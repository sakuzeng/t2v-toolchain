"""生图 prompt 的解析与校验：frontmatter 字段、@别名参考图、target、默认值。"""
import pytest

from conftest import patch_config
from t2v.engines.flux import prompt as flux_prompt
from t2v.errors import ProjectError

IMAGE_PROMPT = """---
id: demo-project/scene/living-room
kind: image
target: assets/canonical/scenes/plate.png
references:
  - "@plate_ref"
aspect: 9:16
megapixels: 1.0
steps: 4
status: pending
---

Photorealistic still photograph, vertical 9:16, an empty warm room.
"""


NO_REF_PROMPT = """---
id: demo-project/scene/room
kind: image
aspect: 9:16
steps: 4
---

Photorealistic still photograph of an empty room.
"""


def write_image_prompt(project, relative, text=IMAGE_PROMPT):
    target = project / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def test_spec_reads_frontmatter_and_resolves_aliases(demo_project):
    reference = demo_project / "assets" / "canonical" / "characters" / "plate.png"
    reference.write_bytes(b"png")
    patch_config(demo_project, assets={"plate_ref": {"path": "assets/canonical/characters/plate.png"}})
    write_image_prompt(demo_project, "prompts/scene/living-room/v001.md")
    spec = flux_prompt.from_file("demo-project", "prompts/scene/living-room/v001.md")
    assert spec.image_id == "scene-living-room"
    assert spec.aspect == "9:16" and spec.steps == 4 and spec.cfg == 1.0
    assert spec.references == [reference]
    assert spec.target == demo_project / "assets" / "canonical" / "scenes" / "plate.png"
    assert spec.prompt_text.startswith("Photorealistic still photograph")
    assert "---" not in spec.prompt_text          # frontmatter 不进正文
    assert spec.prefix == "flux2/scene-living-room"


def test_defaults_are_the_distilled_klein_settings(demo_project):
    write_image_prompt(demo_project, "prompts/scene/room/v001.md",
                       NO_REF_PROMPT.replace("aspect: 9:16\n", "").replace("steps: 4\n", ""))
    spec = flux_prompt.from_file("demo-project", "prompts/scene/room/v001.md")
    assert spec.steps == 4 and spec.cfg == 1.0 and spec.aspect == "1:1"
    assert spec.unet == "flux-2-klein-9b.safetensors"
    assert spec.clip == "qwen_3_8b_fp8mixed.safetensors"
    assert spec.vae == "flux2-vae.safetensors"


def test_missing_reference_file_is_an_error(demo_project):
    write_image_prompt(demo_project, "prompts/scene/room/v001.md",
                       IMAGE_PROMPT.replace('"@plate_ref"', "assets/canonical/scenes/nope.png"))
    spec = flux_prompt.from_file("demo-project", "prompts/scene/room/v001.md")
    errors, _ = flux_prompt.validate(spec)
    assert any("缺少输入" in error for error in errors)


def test_empty_body_and_missing_file_are_reported(demo_project):
    write_image_prompt(demo_project, "prompts/scene/room/v001.md", "---\nid: demo/x\n---\n\n")
    with pytest.raises(ProjectError, match="正文是空的"):
        flux_prompt.from_file("demo-project", "prompts/scene/room/v001.md")
    with pytest.raises(ProjectError, match="找不到生图 prompt"):
        flux_prompt.from_file("demo-project", "prompts/scene/none/v001.md")


def test_bad_aspect_is_reported_by_validate(demo_project):
    write_image_prompt(demo_project, "prompts/scene/room/v001.md",
                       NO_REF_PROMPT.replace("aspect: 9:16", "aspect: portrait"))
    spec = flux_prompt.from_file("demo-project", "prompts/scene/room/v001.md")
    errors, _ = flux_prompt.validate(spec)
    assert any("aspect" in error for error in errors)
