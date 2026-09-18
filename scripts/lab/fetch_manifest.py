#!/usr/bin/env python3
"""并行分块下载器：按 sha256 清单下载 H3 权重，边下边校验。

为什么实验室链路不用 aria2c：同一个 modelscope URL，aria2c 1.36 在实验室容器里只有
5.3–6.0 MB/s（20 GB 文件 ETA ≈ 53 分钟），python-urllib 也只有 0.4–0.6 MB/s，
而 curl 单连接 22–39 MB/s、8 并发聚合 121 MB/s。所以这里用 curl 取数据、自己并发分块，
20 GB 文件约 2 分钟。原因未完全定位（不是 UA、不是 HTTP/1.1），见 docs/ops/PITFALLS.md。
AutoDL 侧仍用 scripts/remote/models/h3/download.sh（aria2）。

特性：64 MB 分块并发、pwrite 落盘（不额外占盘）、`.progress.json` 断点续传、
完成后写 `<file>.sha256.ok` 标记（与 aria2 版脚本互相兼容）。

用法：
  python3 fetch_manifest.py --manifest manifest.txt --dest-root ~/workspace/ComfyUI/models [--workers 8] [--verify-only]
  SRC=hfmirror python3 fetch_manifest.py ...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

CHUNK = 64 * 1024 * 1024          # 分块大小
BLOCK = 4 * 1024 * 1024           # 单次读取块
BASES = {
    "modelscope": "https://www.modelscope.cn/models/{repo}/resolve/master",
    "hfmirror": "https://hf-mirror.com/{repo}/resolve/main",
    "hf": "https://huggingface.co/{repo}/resolve/main",
}


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def fetch_chunk(url: str, dst: str, start: int, end: int, tries: int = 4) -> int:
    """用 curl 取 [start, end] 字节并 pwrite 到 dst，返回写入字节数。

    走 curl 而不是 urllib：modelscope 对 python-urllib 的响应只有 0.4–0.6 MB/s，
    同样 URL 的 curl 有 22–39 MB/s（见 docs/ops/PITFALLS.md）。
    必须带 -L：modelscope 现在对 LFS 请求回 302 跳到 cdn-lfs-cn-*.modelscope.cn（带签名
    auth_key），不跟随就只拿到 375 字节的跳转页，被当成短读。
    """
    last = None
    for attempt in range(1, tries + 1):
        proc = None
        try:
            proc = subprocess.Popen(
                ["curl", "-sSL", "--fail", "--max-time", "600",
                 "-r", f"{start}-{end}", url],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            written = 0
            fd = os.open(dst, os.O_WRONLY)
            try:
                while True:
                    block = proc.stdout.read(BLOCK)
                    if not block:
                        break
                    os.pwrite(fd, block, start + written)
                    written += len(block)
            finally:
                os.close(fd)
            rc = proc.wait()
            err = proc.stderr.read().decode("utf-8", "replace").strip()[:200]
            if rc != 0:
                raise IOError(f"curl 退出码 {rc}: {err}")
            if written != end - start + 1:
                raise IOError(f"短读：{written} != {end - start + 1} {err}")
            return written
        except Exception as exc:                       # noqa: BLE001 - 网络异常统一重试
            last = exc
            if proc is not None and proc.poll() is None:
                proc.kill()
                proc.wait()
            if attempt < tries:
                time.sleep(2 * attempt)
    raise IOError(f"分块 {start}-{end} 失败：{last}")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def plan_chunks(size: int) -> list[tuple[int, int]]:
    return [(s, min(s + CHUNK - 1, size - 1)) for s in range(0, size, CHUNK)]


def download_one(url: str, dst: str, size: int, sha: str, workers: int) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    state_path = dst + ".progress.json"
    chunks = plan_chunks(size)
    done: set[int] = set()

    if os.path.exists(state_path) and os.path.exists(dst):
        try:
            st = json.load(open(state_path))
            if st.get("size") == size and st.get("chunk") == CHUNK:
                done = set(st.get("done", []))
        except Exception:                              # noqa: BLE001 - 状态坏了就重来
            done = set()
    if not os.path.exists(dst) or not done:
        # 没有可信的续传状态（例如 aria2 留下的稀疏半成品）→ 截断重下
        with open(dst, "wb"):
            pass
        done = set()
    if not os.path.exists(dst):
        with open(dst, "wb"):
            pass

    todo = [(i, chunks[i]) for i in range(len(chunks)) if i not in done]
    have = sum(chunks[i][1] - chunks[i][0] + 1 for i in done)
    if not todo:
        print(f"  分块已齐，直接校验", flush=True)
    else:
        lock = threading.Lock()
        counter = {"bytes": have, "n": len(done)}
        t0 = time.time()
        stop = threading.Event()

        def reporter() -> None:
            while not stop.wait(5):
                with lock:
                    b, n = counter["bytes"], counter["n"]
                el = time.time() - t0
                rate = (b - have) / el if el > 0 else 0
                pct = 100 * b / size if size else 100
                eta = (size - b) / rate if rate > 0 else 0
                print(f"  {pct:5.1f}%  {human(b)}/{human(size)}  {human(rate)}/s  "
                      f"分块 {n}/{len(chunks)}  ETA {eta/60:.1f}min", flush=True)

        abort = threading.Event()

        def work(item: tuple[int, tuple[int, int]]) -> None:
            if abort.is_set():                         # 已判定失败，剩余分块直接快进，不再空转
                return
            idx, (s, e) = item
            try:
                fetch_chunk(url, dst, s, e)
            except Exception:
                abort.set()
                raise
            with lock:
                done.add(idx)
                counter["bytes"] += e - s + 1
                counter["n"] += 1
                if counter["n"] % 4 == 0 or counter["n"] == len(chunks):
                    json.dump({"size": size, "chunk": CHUNK, "done": sorted(done)},
                              open(state_path, "w"))

        print(f"  {len(todo)} 个分块 × {human(CHUNK)}，{workers} 并发", flush=True)
        th = threading.Thread(target=reporter, daemon=True)
        th.start()
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for fut in [pool.submit(work, it) for it in todo]:
                    fut.result()
        finally:
            stop.set()
        with lock:
            b = counter["bytes"]
        print(f"  下载完成 {human(b)}，用时 {(time.time()-t0)/60:.1f} 分钟", flush=True)

    actual = os.path.getsize(dst)
    if actual != size:
        raise IOError(f"尺寸不符：{actual} != {size}")
    print(f"  校验 sha256 …", flush=True)
    got = sha256_file(dst)
    if got != sha:
        os.remove(state_path) if os.path.exists(state_path) else None
        raise IOError(f"sha256 不符：{got} != {sha}（删掉 {dst} 后重跑）")
    with open(dst + ".sha256.ok", "w") as fh:
        fh.write(sha)
    for tmp in (state_path,):
        if os.path.exists(tmp):
            os.remove(tmp)
    print(f"  OK {os.path.basename(dst)}", flush=True)


def parse_entry(line: str, default_repo: str) -> tuple[str, int, str, str, str]:
    """解析一行清单 → (sha256, 字节数, 落盘路径, 仓库内路径, 仓库)。

    格式（后两列可省）：`sha256  字节数  落盘路径  [仓库内路径]  [仓库]`
    - 落盘路径：相对 ComfyUI/models
    - 仓库内路径：默认与落盘路径相同（Comfy-Org 那类仓库把权重放在 `split_files/` 下，
      两者不同；少了这列就会down到 models/split_files/... 里，加载器找不到）
    - 仓库：默认取 --repo，一份清单因此可以跨多个仓库
    """
    parts = line.split()
    if len(parts) == 3:
        sha, size, dest = parts
        src_path, repo = dest, default_repo
    elif len(parts) == 4:
        sha, size, dest, src_path = parts
        repo = default_repo
    elif len(parts) == 5:
        sha, size, dest, src_path, repo = parts
    else:
        raise ValueError(f"清单行需要 3–5 列，实际 {len(parts)} 列：{line}")
    return sha, int(size), dest, src_path, repo


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--dest-root", required=True, help="相当于 ComfyUI/models")
    ap.add_argument("--repo", default=os.environ.get("REPO", "Comfy-Org/MiniMax-H3"))
    ap.add_argument("--src", default=os.environ.get("SRC", "modelscope"), choices=sorted(BASES))
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", "8")))
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()

    base = BASES[args.src]
    fail = 0
    entries = []
    for line in open(args.manifest, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.append(parse_entry(line, args.repo))

    for sha, size, dest, src_path, repo in entries:
        dst = os.path.join(args.dest_root, dest)
        marker = dst + ".sha256.ok"
        if os.path.exists(marker) and open(marker).read().strip() == sha:
            print(f"skip (verified) {dest}", flush=True)
            continue
        print(f"[{dest}] {human(size)}", flush=True)
        try:
            if args.verify_only:
                if not os.path.exists(dst):
                    raise IOError("文件不存在")
                if os.path.getsize(dst) != size:
                    raise IOError("尺寸不符")
                if sha256_file(dst) != sha:
                    raise IOError("sha256 不符")
                with open(marker, "w") as fh:
                    fh.write(sha)
                print("  OK", flush=True)
            else:
                url = f"{base.format(repo=repo)}/{src_path}"
                download_one(url, dst, size, sha, args.workers)
        except Exception as exc:                       # noqa: BLE001 - 单个文件失败不中断整批
            print(f"  失败：{exc}", flush=True)
            fail += 1

    print("全部通过" if fail == 0 else f"有 {fail} 个文件失败", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
