"""实验室下载器 `scripts/lab/fetch_manifest.py` 的行为测试（离线，不联网）。

这个脚本是实验室链路唯一的权重入口，所以把"分块覆盖是否完整、断点续传是否真的跳过已下分块、
sha256 标记是否落地"三件事钉住；真实的网络/302 行为只能靠 docs/ops/PITFALLS.md 的实测记录。
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from t2v.paths import ROOT

LAB = ROOT / "scripts/lab"


def _load(name: str = "fetch_manifest"):
    spec = importlib.util.spec_from_file_location(name, LAB / "fetch_manifest.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def fm():
    return _load()


@pytest.fixture
def small_chunks(fm, monkeypatch):
    """把分块缩到 256 B，免得测试造 MB 级文件。"""
    monkeypatch.setattr(fm, "CHUNK", 256)
    monkeypatch.setattr(fm, "BLOCK", 64)
    return 256


def fake_writer(fm, monkeypatch, calls):
    """假的 fetch_chunk：按请求区间写入确定性内容，并记录被请求的区间。"""

    def fetch(url, dst, start, end, tries=4):
        calls.append((start, end))
        import os

        fd = os.open(dst, os.O_WRONLY)
        try:
            os.pwrite(fd, bytes([(start + i) % 251 for i in range(end - start + 1)]), start)
        finally:
            os.close(fd)
        return end - start + 1

    monkeypatch.setattr(fm, "fetch_chunk", fetch)


def expected_bytes(size: int) -> bytes:
    return bytes([i % 251 for i in range(size)])


def test_plan_chunks_covers_whole_file(fm):
    size = 1000
    chunks = fm.plan_chunks(size)
    # 无缝无重叠地覆盖 [0, size)
    assert chunks[0][0] == 0
    assert chunks[-1][1] == size - 1
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:]):
        assert next_start == prev_end + 1


def test_plan_chunks_exact_multiple(fm):
    chunks = fm.plan_chunks(512)          # 假设 CHUNK=256 的整数倍场景
    assert all(0 <= s <= e for s, e in chunks)


def test_human_units(fm):
    assert fm.human(512) == "512.0B"
    assert fm.human(1024) == "1.0KB"
    assert fm.human(20 * 1024 ** 3).endswith("GB")


def test_download_writes_data_verifies_and_marks(fm, tmp_path, small_chunks, monkeypatch):
    size = 700
    body = expected_bytes(size)
    sha = hashlib.sha256(body).hexdigest()
    calls = []
    fake_writer(fm, monkeypatch, calls)
    dst = str(tmp_path / "w.safetensors")

    fm.download_one("http://example.invalid/f", dst, size, sha, workers=2)

    assert Path(dst).read_bytes() == body
    assert Path(dst + ".sha256.ok").read_text() == sha
    assert not Path(dst + ".progress.json").exists()      # 完成后清掉续传状态
    # 三个分块都请求到了（不重不漏）
    assert sum(e - s + 1 for s, e in calls) == size


def test_download_resumes_from_state(fm, tmp_path, small_chunks, monkeypatch):
    size = 768                                             # 3 × 256
    body = expected_bytes(size)
    sha = hashlib.sha256(body).hexdigest()
    dst = tmp_path / "w.safetensors"
    dst.write_bytes(body)
    calls = []
    fake_writer(fm, monkeypatch, calls)
    # 假装第 0、2 块早已下好，只剩第 1 块
    (tmp_path / "w.safetensors.progress.json").write_text(
        json.dumps({"size": size, "chunk": small_chunks, "done": [0, 2]}))

    fm.download_one("http://example.invalid/f", str(dst), size, sha, workers=2)

    assert calls == [(256, 511)]                           # 只补了缺的那块
    assert Path(str(dst) + ".sha256.ok").read_text() == sha


def test_download_reports_sha_mismatch(fm, tmp_path, small_chunks, monkeypatch):
    size = 256
    calls = []
    fake_writer(fm, monkeypatch, calls)
    dst = str(tmp_path / "bad.safetensors")

    with pytest.raises(IOError, match="sha256 不符"):
        fm.download_one("http://example.invalid/f", dst, size, "0" * 64, workers=1)
    assert not Path(dst + ".sha256.ok").exists()


def test_manifest_layout_matches_downloader(fm):
    """清单三列格式（sha256 size path）必须能被解析，且路径都是相对 ComfyUI/models 的。"""
    rows = [l.split() for l in (LAB / "../remote/models/h3/manifest.txt").read_text().splitlines()
            if l.strip() and not l.startswith("#")]
    assert len(rows) >= 17
    for sha, size, path in rows:
        assert len(sha) == 64 and int(size) > 0
        assert not path.startswith("/")
        assert path.split("/")[0] in {"diffusion_models", "text_encoders", "vae", "loras", "embeddings"}
