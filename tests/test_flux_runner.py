"""flux 执行链路：用假 ComfyUI 走完上传—提交—轮询—下载—记账，验证 run capsule。"""
import json

import pytest

from t2v.engines.flux import prompt as flux_prompt
from t2v.engines.flux import runner as flux_runner
from t2v.errors import CostGuardError

ENTRY = {
    "status": {"completed": True, "status_str": "success", "messages": [
        ["execution_start", {"timestamp": 1000}],
        ["execution_success", {"timestamp": 31000}],
    ]},
    "outputs": {"13": {"images": [{"filename": "klein_00001_.png", "subfolder": "flux2",
                                   "type": "output"}]}},
}

IMAGE_PROMPT = """---
id: demo-project/keyframe/s01
kind: keyframe
target: assets/canonical/keyframes/s01.png
references:
  - "@plate_ref"
aspect: 9:16
---

A young woman curled up in a warm room, vertical 9:16.
"""


class FakeComfy:
    """只实现 runner 用到的那几个方法；任何真实网络调用都会 AttributeError。"""

    def __init__(self):
        self.uploaded, self.submitted = [], []

    def browser_client_id(self, want="auto"):
        return "browser-session"

    def device(self):
        return {"name": "Fake A6000", "vram_free": 48 * 2 ** 30}

    def upload(self, path):
        self.uploaded.append(str(path))
        return {"name": "uploaded_" + str(path).rsplit("/", 1)[-1], "subfolder": "", "type": "input"}

    def submit(self, graph, client_id=None, extra_data=None):
        self.submitted.append(graph)
        return "ffff000011112222"

    def wait(self, prompt_id, started_at=None):
        return ENTRY

    outputs = staticmethod(lambda entry: [item for values in entry["outputs"].values()
                                          for items in values.values() for item in items])
    download = staticmethod(lambda item: b"\x89PNG\r\n\x1a\n fake")
    exec_seconds = staticmethod(lambda entry: 30.0)


@pytest.fixture
def image_spec(demo_project):
    from conftest import patch_config
    reference = demo_project / "assets" / "canonical" / "scenes" / "plate.png"
    reference.parent.mkdir(parents=True, exist_ok=True)
    reference.write_bytes(b"png")
    patch_config(demo_project, assets={"plate_ref": {"path": "assets/canonical/scenes/plate.png"}},
                 cost={"currency": "CNY", "gpu_hourly": 2.88,
                       "estimated_render_minutes_per_second": {"1.0": 0.5}})
    path = demo_project / "prompts" / "shots" / "s01" / "keyframe.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(IMAGE_PROMPT, encoding="utf-8")
    return flux_prompt.from_file("demo-project", "prompts/shots/s01/keyframe.md",
                                 {"seed": 202})


def test_execute_refuses_without_confirmation(demo_project, image_spec):
    with pytest.raises(CostGuardError, match="占卡保护"):
        flux_runner.execute(image_spec, client=FakeComfy(), cost_confirmed=False)


def test_execute_uploads_reference_and_writes_a_capsule(demo_project, image_spec):
    client = FakeComfy()
    sidecar = flux_runner.execute(image_spec, client=client, cost_confirmed=True)

    assert client.uploaded == [str(image_spec.references[0])]
    assert client.submitted[0]["ref0_load"]["inputs"]["image"].startswith("uploaded_")
    assert client.submitted[0]["10"]["inputs"]["noise_seed"] == 202

    capsule = demo_project / "runs" / "keyframe-s01" / sidecar["run_id"]
    assert (capsule / "output.png").read_bytes().startswith(b"\x89PNG")
    assert (capsule / "prompt.md").read_text(encoding="utf-8").startswith("---")
    assert json.loads((capsule / "workflow.api.json").read_text(encoding="utf-8"))["13"]["class_type"] == "SaveImage"
    assert sidecar["params"]["width"] == 768 and sidecar["params"]["height"] == 1344
    assert sidecar["exec_seconds"] == 30.0
    row = json.loads((demo_project / "runs" / "index.jsonl").read_text(encoding="utf-8").strip())
    assert row["resolution"] == "768x1344" and row["seed"] == 202
    assert not image_spec.target.exists()          # 默认不写正式路径，等评审后再 --write-target


def test_write_target_promotes_the_image(demo_project, image_spec):
    flux_runner.execute(image_spec, client=FakeComfy(), cost_confirmed=True, write_target=True)
    assert image_spec.target.read_bytes().startswith(b"\x89PNG")
