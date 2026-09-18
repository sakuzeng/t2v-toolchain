"""项目 + 镜头 → H3Request，以及免费报价。"""
import pytest

from conftest import VALID_PROMPT, patch_config, write_prompt
from t2v import paths
from t2v.engines.h3 import request as request_mod
from t2v.errors import ProjectError


def test_project_shot_resolves_to_a_complete_request(demo_project):
    request = request_mod.from_project("demo-project", "c001")
    assert request.shot == "c001" and request.name == "c001"
    assert request.prompt_path.name == "v001.md"
    assert request.workflow == paths.ROOT / "workflows/h3/r2v.api.json"
    assert request.duration == 3.0 and request.frames == 73
    assert request.megapixels == 0.4 and request.steps == 20
    assert request.capsule is True
    assert request.capsule_root == demo_project / "runs"
    assert request.export_ui == demo_project / "workflows" / "c001__v001.ui.json"
    assert request.workflow_label == "c001 · v001"
    assert request.refs == []


def test_latest_version_wins_and_version_flag_pins(demo_project):
    write_prompt(demo_project, "c001", "v002")
    assert request_mod.from_project("demo-project", "c001").prompt_path.name == "v002.md"
    pinned = request_mod.from_project("demo-project", "c001", {"version": "v001"})
    assert pinned.prompt_path.name == "v001.md"


def test_command_line_overrides_beat_config(demo_project):
    request = request_mod.from_project("demo-project", "c001",
                                       {"seed": 42, "steps": 8, "megapixels": 0.98, "duration": 2.3})
    assert (request.seed, request.steps, request.megapixels, request.duration) == (42, 8, 0.98, 2.3)


def test_asset_aliases_resolve_inside_the_project(demo_project):
    face = demo_project / "assets" / "canonical" / "characters" / "face.png"
    face.write_bytes(b"png")
    patch_config(demo_project,
                 assets={"face": {"path": "assets/canonical/characters/face.png"}},
                 defaults={"refs": ["@face"]})
    assert request_mod.from_project("demo-project", "c001").refs == [face]


def test_first_frame_comes_from_frontmatter_or_defaults(demo_project):
    """I2V 的首帧是逐镜不同的图，所以走 frontmatter；项目级默认值可选。"""
    frame = demo_project / "assets" / "canonical" / "keyframes" / "kf-01.png"
    frame.parent.mkdir(parents=True)
    frame.write_bytes(b"png")
    patch_config(demo_project, assets={"kf_01": {"path": "assets/canonical/keyframes/kf-01.png"}})
    write_prompt(demo_project, "c001", "v002",
                 VALID_PROMPT.replace("status: draft", 'status: draft\nfirst_frame: "@kf_01"'))
    request = request_mod.from_project("demo-project", "c001")
    assert request.first_frame == frame and frame in request.input_paths()


def test_unknown_alias_and_missing_duration_are_reported(demo_project):
    patch_config(demo_project, defaults={"refs": ["@nope"]})
    with pytest.raises(ProjectError, match="未知资产别名"):
        request_mod.from_project("demo-project", "c001")
    write_prompt(demo_project, "c002", "v001", "---\nstatus: draft\n---\nsummary:\n x\n")
    with pytest.raises(ProjectError, match="duration"):
        request_mod.from_project("demo-project", "c002")


def test_missing_shot_is_reported(demo_project):
    with pytest.raises(ProjectError, match="找不到镜头"):
        request_mod.from_project("demo-project", "c999")


def test_quote_needs_a_measured_baseline(demo_project):
    request = request_mod.from_project("demo-project", "c001")
    assert "尚未配置" in request_mod.quote(request)          # 模板里 gpu_hourly = 0
    patch_config(demo_project, cost={"currency": "CNY", "gpu_hourly": 2.78, "startup_minutes": 2,
                                     "estimated_render_minutes_per_second": {"0.4": 1.5}})
    text = request_mod.quote(request_mod.from_project("demo-project", "c001"))
    assert "渲染约 4.5 分钟" in text and "¥" in text


def test_only_versioned_files_are_read_as_prompts(demo_project):
    """中文剧本 script.md 与 prompt 同目录，绝不能被当成 prompt 送给模型。"""
    shot = demo_project / "prompts" / "shots" / "c001"
    (shot / "script.md").write_text("# 中文剧本\n\n场景环境：不该出现在正文里。\n", encoding="utf-8")
    (shot / "notes.md").write_text("随手笔记\n", encoding="utf-8")
    request = request_mod.from_project("demo-project", "c001")
    assert request.prompt_path.name == "v001.md"
    assert "场景环境" not in request.prompt_text
