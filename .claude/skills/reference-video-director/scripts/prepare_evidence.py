#!/usr/bin/env python3
"""取证层：为参考视频分析生成可复现的 FFmpeg 证据包。

只依赖标准库 + ffmpeg/ffprobe（时间码烧录在有 opencv 时自动启用）。不解释电影语言，只记录源文件身份并产出供人/导演分析的帧。

用法：
  python3 prepare_evidence.py REF.mp4 --output-dir DIR
      [--compare ATTEMPT.mp4] [--compare-map 参考t:产物t,...]   # 分段线性时间映射；不给则假定同速同起点
      [--dense-window 起:止 ...] [--dense-fps 24]               # 手动密集窗口
      [--auto-windows/--no-auto-windows] [--cut-margin 0.35]    # 默认在每个候选切点 ±margin 自动生成密集窗口
      [--sample-fps 2] [--compare-fps 4] [--scene-threshold 0.28]
      [--max-frames-per-window 48] [--no-stamp] [--overwrite]

产物：coarse/（粗采样帧）、contact-sheets/、dense/window_XX_起-止/（密集帧）、matched-reference-left_attempt-right/、manifest.json。
帧文件名里的时间来自 ffmpeg showinfo 的真实 pts（源相对时间），不是按序号推算。
候选切点只是场景分数，必须用 measure_tracks.py 的 cuts.json 或密集帧复核；快速甩镜会产生成串误报。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

PTS_RE = re.compile(r"pts_time:([0-9.]+)")


def command(argv: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv, check=True, text=True,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict:
    result = command(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], capture=True)
    data = json.loads(result.stdout)
    stream = next((item for item in data.get("streams", []) if item.get("codec_type") == "video"), {})
    duration = float(stream.get("duration") or data.get("format", {}).get("duration") or 0)
    return {
        "path": str(path.resolve()), "sha256": sha256(path), "duration": duration,
        "width": stream.get("width"), "height": stream.get("height"),
        "avg_frame_rate": stream.get("avg_frame_rate"), "r_frame_rate": stream.get("r_frame_rate"),
        "nb_frames": stream.get("nb_frames"), "codec_name": stream.get("codec_name"),
        "has_audio": any(item.get("codec_type") == "audio" for item in data.get("streams", [])),
    }


def ensure_empty(path: Path, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not overwrite:
            raise RuntimeError(f"输出目录非空：{path}（加 --overwrite）")
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def detect_cuts(video: Path, threshold: float) -> list[float]:
    result = command(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", f"select=gt(scene\\,{threshold}),showinfo", "-an", "-f", "null", "-"], capture=True)
    return sorted({round(float(value), 6) for value in PTS_RE.findall(result.stderr)})


def try_stamp(path: Path, text: str) -> bool:
    """在帧左下角烧录时间码；没有 opencv 时静默跳过。"""
    try:
        import cv2  # type: ignore
    except Exception:
        return False
    img = cv2.imread(str(path))
    if img is None:
        return False
    h = img.shape[0]
    cv2.rectangle(img, (0, h - 26), (12 + 11 * len(text), h), (0, 0, 0), -1)
    cv2.putText(img, text, (6, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(str(path), img)
    return True


def extract_frames(video: Path, folder: Path, fps: float, start: float = 0, end: float | None = None, *, stamp: bool, label: str = "") -> list[dict]:
    folder.mkdir(parents=True, exist_ok=True)
    argv = ["ffmpeg", "-hide_banner", "-loglevel", "info", "-y"]
    if start:
        argv.extend(["-ss", f"{start:.6f}"])
    argv.extend(["-i", str(video)])
    if end is not None:
        argv.extend(["-t", f"{end - start:.6f}"])
    argv.extend(["-vf", f"fps={fps},scale='min(960,iw)':-2,showinfo", "-q:v", "2", str(folder / "frame_%04d.jpg")])
    result = command(argv, capture=True)
    pts = [float(v) for v in PTS_RE.findall(result.stderr)]
    entries = []
    for index, old in enumerate(sorted(folder.glob("frame_*.jpg"))):
        # -ss 输入定位后 showinfo 的 pts 从 0 起算，加回 start 得到源相对时间
        timestamp = (pts[index] if index < len(pts) else index / fps) + start
        new = folder / f"frame_{index + 1:04d}_t{timestamp:08.3f}.jpg"
        old.rename(new)
        if stamp:
            try_stamp(new, f"{label}t={timestamp:.3f}s")
        entries.append({"file": str(new), "time": round(timestamp, 6)})
    return entries


def make_sheets(video: Path, pattern: Path, fps: float, cols: int, rows: int) -> None:
    pattern.parent.mkdir(parents=True, exist_ok=True)
    command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
             "-vf", f"fps={fps},scale=360:-2,tile={cols}x{rows}:padding=8:margin=8", "-q:v", "2", "-vsync", "vfr", str(pattern)])


def parse_map(text: str | None):
    """'参考t:产物t,...' → 分段线性函数 参考时间→产物时间；None → 恒等。"""
    if not text:
        return None
    pairs = sorted(tuple(float(v) for v in p.split(":")) for p in text.split(","))
    if len(pairs) < 2:
        raise argparse.ArgumentTypeError("--compare-map 至少两对，如 0:0,2.3:2.3,2.875:3.042")

    def fn(t: float) -> float:
        if t <= pairs[0][0]:
            return pairs[0][1]
        for (a, b), (c, d) in zip(pairs, pairs[1:]):
            if t <= c:
                return b + (t - a) * (d - b) / max(1e-9, (c - a))
        return pairs[-1][1]
    fn.pairs = pairs  # type: ignore[attr-defined]
    return fn


def make_matched_frames(primary: Path, candidate: Path, folder: Path, fps: float, duration: float, cmap, *, stamp: bool) -> list[dict]:
    """参考在左、产物在右；每一对按时间映射分别定位后并排，适用于两条视频节奏不同的情形。"""
    folder.mkdir(parents=True, exist_ok=True)
    entries = []
    count = int(duration * fps) + 1
    for index in range(count):
        t_ref = index / fps
        if t_ref > duration:
            break
        t_att = cmap(t_ref) if cmap else t_ref
        out = folder / f"frame_{index + 1:04d}_t{t_ref:08.3f}_att{t_att:07.3f}.jpg"
        command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                 "-ss", f"{t_ref:.6f}", "-i", str(primary), "-ss", f"{t_att:.6f}", "-i", str(candidate),
                 "-filter_complex", "[0:v]scale=-2:360[a];[1:v]scale=-2:360[b];[a][b]hstack=inputs=2[v]",
                 "-map", "[v]", "-frames:v", "1", "-q:v", "2", str(out)])
        if out.exists():
            if stamp:
                try_stamp(out, f"ref t={t_ref:.3f}s | attempt t={t_att:.3f}s")
            entries.append({"file": str(out), "ref_time": round(t_ref, 6), "attempt_time": round(t_att, 6)})
    return entries


def parse_window(value: str) -> tuple[float, float]:
    try:
        start_text, end_text = value.split(":", 1)
        start, end = float(start_text), float(end_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("窗口格式为 起:止（秒）") from exc
    if start < 0 or end <= start:
        raise argparse.ArgumentTypeError("窗口须满足 0 <= 起 < 止")
    return start, end


def merge_windows(windows: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for a, b in sorted(windows):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--compare-map", type=parse_map, default=None)
    parser.add_argument("--sample-fps", type=float, default=2.0)
    parser.add_argument("--dense-window", action="append", type=parse_window, default=[])
    parser.add_argument("--dense-fps", type=float, default=24.0)
    parser.add_argument("--auto-windows", dest="auto_windows", action="store_true", default=True)
    parser.add_argument("--no-auto-windows", dest="auto_windows", action="store_false")
    parser.add_argument("--cut-margin", type=float, default=0.35)
    parser.add_argument("--compare-fps", type=float, default=4.0)
    parser.add_argument("--scene-threshold", type=float, default=0.28)
    parser.add_argument("--sheet-cols", type=int, default=4)
    parser.add_argument("--sheet-rows", type=int, default=5)
    parser.add_argument("--max-frames-per-window", type=int, default=48)
    parser.add_argument("--total-frame-budget", type=int, default=160, help="超过只警告，不阻止")
    parser.add_argument("--no-stamp", dest="stamp", action="store_false", default=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    for binary in ("ffmpeg", "ffprobe"):
        if shutil.which(binary) is None:
            parser.error(f"缺少可执行文件：{binary}")
    if not args.video.is_file():
        parser.error(f"视频不存在：{args.video}")
    if args.compare and not args.compare.is_file():
        parser.error(f"对比视频不存在：{args.compare}")
    for label, value in (("sample-fps", args.sample_fps), ("dense-fps", args.dense_fps), ("compare-fps", args.compare_fps)):
        if value <= 0:
            parser.error(f"--{label} 必须为正")

    ensure_empty(args.output_dir, args.overwrite)
    primary_probe = probe(args.video)
    comparison_probe = probe(args.compare) if args.compare else None
    duration = primary_probe["duration"]
    notes: list[str] = []

    candidate_cuts = detect_cuts(args.video, args.scene_threshold)

    coarse = extract_frames(args.video, args.output_dir / "coarse", args.sample_fps, stamp=args.stamp)
    make_sheets(args.video, args.output_dir / "contact-sheets" / "sheet_%03d.jpg", args.sample_fps, args.sheet_cols, args.sheet_rows)

    windows = list(args.dense_window)
    if args.auto_windows:
        windows += [(max(0.0, c - args.cut_margin), min(duration, c + args.cut_margin)) for c in candidate_cuts]
    windows = merge_windows([(a, min(b, duration)) for a, b in windows if a < duration])

    dense = []
    for index, (start, end) in enumerate(windows, 1):
        fps = args.dense_fps
        if (end - start) * fps > args.max_frames_per_window:
            fps = args.max_frames_per_window / (end - start)
            notes.append(f"窗口 {start:.3f}-{end:.3f} 按 {args.dense_fps} fps 超过 {args.max_frames_per_window} 帧，降到 {fps:.2f} fps；要看更细请缩小窗口")
        folder = args.output_dir / "dense" / f"window_{index:02d}_{start:.3f}-{end:.3f}"
        dense.append({"start": start, "end": end, "fps": fps, "frames": extract_frames(args.video, folder, fps, start, end, stamp=args.stamp)})

    matched = []
    if args.compare:
        cmap = args.compare_map
        def last_frame_time(pr):
            num, den = (pr.get("r_frame_rate") or "24/1").split("/")
            fps_ = float(num) / float(den or 1)
            return max(0.0, pr["duration"] - 1.0 / fps_)
        if cmap is None:
            notes.append("未给 --compare-map：并排帧假定产物与参考同起点同速；若产物做过时间重采样，2 条时间线会错位")
            span = min(last_frame_time(primary_probe), last_frame_time(comparison_probe))
        else:
            span = min(last_frame_time(primary_probe), cmap.pairs[-1][0])
            while span > 0 and cmap(span) > last_frame_time(comparison_probe):
                span -= 1.0 / args.compare_fps
        matched = make_matched_frames(args.video, args.compare, args.output_dir / "matched-reference-left_attempt-right", args.compare_fps, span, cmap, stamp=args.stamp)

    total_frames = len(coarse) + sum(len(d["frames"]) for d in dense) + len(matched)
    if total_frames > args.total_frame_budget:
        notes.append(f"证据帧共 {total_frames} 张，超过单次阅读预算 {args.total_frame_budget}；分窗口分批看，或先看 contact-sheets 与 measure_tracks 的曲线再挑窗口")
    if not args.stamp:
        notes.append("未烧录时间码")
    else:
        try:
            import cv2  # noqa: F401
        except Exception:
            notes.append("当前解释器没有 opencv，时间码未烧录；用 text2video 虚拟环境的 python 运行可启用")

    manifest = {
        "schema_version": 2,
        "reference": primary_probe,
        "comparison": comparison_probe,
        "compare_map": [list(p) for p in args.compare_map.pairs] if args.compare_map else None,
        "sampling": {
            "coarse_fps": args.sample_fps, "dense_fps": args.dense_fps, "compare_fps": args.compare_fps if args.compare else None,
            "dense_windows": [{"start": s, "end": e} for s, e in windows], "auto_windows": args.auto_windows,
            "cut_margin": args.cut_margin, "scene_threshold": args.scene_threshold,
        },
        "candidate_cuts": candidate_cuts,
        "coarse_frames": coarse,
        "dense_samples": dense,
        "matched_frames": matched,
        "notes": [
            "candidate_cuts 是 FFmpeg 场景分数，快速甩镜会连续误报；以 measure_tracks.py 的 cuts.json 判定 + 密集帧目视为准",
            "帧文件名中的时间是 showinfo 真实 pts（源相对）",
            "并排帧：左参考、右产物；文件名含两侧各自的时间",
        ] + notes,
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output_dir": str(args.output_dir), "duration": duration, "candidate_cuts": candidate_cuts,
        "dense_windows": [[round(s, 3), round(e, 3)] for s, e in windows],
        "coarse_frames": len(coarse), "dense_frames": sum(len(d["frames"]) for d in dense), "matched_frames": len(matched),
        "notes": notes,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"媒体命令失败：{exc}", file=sys.stderr)
        raise SystemExit(2)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)
