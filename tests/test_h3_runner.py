"""H3 执行链路：用假 ComfyUI 走完提交—轮询—下载—记账，验证 run capsule 的内容。"""
import json

import pytest

from t2v.engines.h3 import request as request_mod
from t2v.engines.h3 import runner as h3_runner
from t2v.errors import CostGuardError

ENTRY = {
    "status": {"completed": True, "status_str": "success", "messages": [
        ["execution_start", {"timestamp": 1000}],
        ["execution_success", {"timestamp": 121000}],
    ]},
    "outputs": {"92": {"video": [{"filename": "c001_00001.mp4", "subfolder": "video", "type": "output"}]}},
}


class FakeComfy:
    """只实现 runner 用到的那几个方法，任何真实网络调用都会 AttributeError。"""

    def __init__(self):
        self.uploaded, self.submitted = [], []

    def browser_client_id(self, want="auto"):
        return "browser-session"

    def device(self):
        return {"name": "Fake 5090", "vram_free": 32 * 2 ** 30}

    def upload(self, path):
        self.uploaded.append(str(path))
        return {"name": "uploaded_" + str(path).rsplit("/", 1)[-1], "subfolder": "", "type": "input"}

    def submit(self, graph, client_id=None, extra_data=None):
        self.submitted.append({"graph": graph, "client_id": client_id, "extra_data": extra_data})
        return "abcdef1234567890"

    def wait(self, prompt_id, started_at=None):
        return ENTRY

    outputs = staticmethod(lambda entry: [item for values in entry["outputs"].values()
                                          for items in values.values() for item in items])
    exec_seconds = staticmethod(lambda entry: 120.0)

    def download(self, item):
        return b"fake-video-bytes"


@pytest.fixture
def prepared_request(demo_project):
    from conftest import patch_config
    ref = demo_project / "assets" / "canonical" / "characters" / "face.png"
    ref.write_bytes(b"png")
    patch_config(demo_project,
                 assets={"face": {"path": "assets/canonical/characters/face.png"}},
                 defaults={"refs": ["@face"]},
                 cost={"currency": "CNY", "gpu_hourly": 2.78, "startup_minutes": 2,
                       "estimated_render_minutes_per_second": {"0.4": 1.5}})
    return request_mod.from_project("demo-project", "c001", {"seed": 20260920})


def test_execute_refuses_without_confirmation(prepared_request):
    client = FakeComfy()
    with pytest.raises(CostGuardError, match="付费保护"):
        h3_runner.execute(prepared_request, client=client, cost_confirmed=False)
    assert client.submitted == []


def test_execute_writes_a_complete_run_capsule(prepared_request, demo_project):
    client = FakeComfy()
    sidecar = h3_runner.execute(prepared_request, client=client, cost_confirmed=True)

    runs = list((demo_project / "runs" / "c001").iterdir())
    assert len(runs) == 1
    run_dir = runs[0]
    assert run_dir.name.endswith("_seed20260920_abcdef12")

    assert (run_dir / "output.mp4").read_bytes() == b"fake-video-bytes"
    assert (run_dir / "prompt.md").read_text(encoding="utf-8").startswith("---")
    assert (run_dir / "logs" / "comfy-status.json").is_file()
    assert (run_dir / "qa").is_dir()
    assert (run_dir / "workflow.ui.json").is_file()

    frozen = json.loads((run_dir / "workflow.api.json").read_text(encoding="utf-8"))
    assert frozen["137"]["inputs"]["image"] == "uploaded_face.png"      # 冻结的是上传后的远端文件名

    request_json = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
    assert request_json["params"]["seed"] == 20260920
    assert [item["sha256"] for item in request_json["inputs"]]          # 每个输入都留了哈希

    assert sidecar["prompt_id"] == "abcdef1234567890"
    assert sidecar["exec_seconds"] == 120.0
    assert sidecar["estimated_render_cost"] == round(120.0 * 2.78 / 3600, 4)
    assert sidecar["device"] == "Fake 5090"

    row = json.loads((demo_project / "runs" / "index.jsonl").read_text(encoding="utf-8").strip())
    assert row["run_id"] == run_dir.name and row["path"] == f"c001/{run_dir.name}"
    assert row["estimated_render_cost"] == sidecar["estimated_render_cost"]


def test_execute_uploads_every_reference_and_submits_with_the_browser_session(prepared_request):
    client = FakeComfy()
    h3_runner.execute(prepared_request, client=client, cost_confirmed=True)
    assert [path.rsplit("/", 1)[-1] for path in client.uploaded] == ["face.png"]
    submission = client.submitted[0]
    assert submission["client_id"] == "browser-session"
    assert submission["extra_data"]["extra_pnginfo"]["workflow"]        # 画布随任务一起提交


def test_index_row_carries_resolution_and_seed(prepared_request, demo_project):
    """挑片要按分辨率/时长/seed 筛，索引就得带上，不该逼人逐个翻 run.json。"""
    import json as _json

    class Probed(FakeComfy):
        pass

    h3_runner.execute(prepared_request, client=Probed(), cost_confirmed=True)
    row = _json.loads((demo_project / "runs" / "index.jsonl").read_text(encoding="utf-8").strip())
    for key in ("resolution", "frames", "duration", "seed"):
        assert key in row, f"索引缺少 {key}"
    assert row["seed"] == 20260920
    assert row["duration"] == 3.0


def test_capsule_dir_is_renamed_to_carry_the_resolution(tmp_path):
    """目录名自带分辨率，挑片时不必逐个翻 run.json。"""
    from t2v.engines.capsule import RunCapsule
    run_id = "20260916-235436_seed101_c075b5d7"
    cap = RunCapsule(tmp_path / "c001" / run_id, index_path=tmp_path / "index.jsonl")
    out = cap.write_bytes("output.mp4", b"x")
    new_id, new_dir, saved = h3_runner._name_with_resolution(
        cap, run_id, cap.dir, [out], {"video": {"width": 864, "height": 480, "frames": 158}})
    assert new_id == "20260916-235436_864x480_seed101_c075b5d7"
    assert new_dir.name == new_id and new_dir.is_dir()
    assert cap.dir == new_dir                       # capsule 内部指针跟着走
    assert saved[0] == new_dir / "output.mp4" and saved[0].is_file()


def test_rename_is_skipped_when_the_probe_found_nothing(tmp_path):
    """ffprobe 缺失或探测失败时保持原名，不能因此丢产物。"""
    from t2v.engines.capsule import RunCapsule
    run_id = "20260916-235436_seed101_c075b5d7"
    cap = RunCapsule(tmp_path / "c001" / run_id)
    out = cap.write_bytes("output.mp4", b"x")
    assert h3_runner._name_with_resolution(cap, run_id, cap.dir, [out], {}) == (run_id, cap.dir, [out])


def test_rename_keeps_request_json_in_step(tmp_path):
    """request.json 在提交时写好、带的是旧 id；改名后必须同步，否则一个 capsule 里两个 id。"""
    import json as _json
    from t2v.engines.capsule import RunCapsule
    run_id = "20260916-235436_seed101_c075b5d7"
    cap = RunCapsule(tmp_path / "c001" / run_id)
    cap.write_json("request.json", {"run_id": run_id, "project": "p"})
    out = cap.write_bytes("output.mp4", b"x")
    new_id, new_dir, _ = h3_runner._name_with_resolution(
        cap, run_id, cap.dir, [out], {"video": {"width": 1344, "height": 768, "frames": 124}})
    assert _json.loads((new_dir / "request.json").read_text(encoding="utf-8"))["run_id"] == new_id
