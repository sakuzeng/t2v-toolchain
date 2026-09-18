"""FLUX.2 [klein] 的建图：尺寸换算、节点接线、参考图串链。"""
import pytest

from t2v.engines.flux import graph as flux_graph
from t2v.engines.flux.prompt import ImageSpec


def spec(**overrides):
    fields = dict(project="demo-project", prompt_path="/tmp/x.md", prompt_text="a quiet room",
                  prompt_id="demo/scene/room", image_id="scene-room", aspect="1:1", megapixels=1.0,
                  steps=4, cfg=1.0)
    fields.update(overrides)
    return ImageSpec(**fields)


def test_latent_size_is_never_below_the_requested_pixels_and_snaps_to_32():
    assert flux_graph.latent_size("1:1", 1.0) == (1024, 1024)
    assert flux_graph.latent_size("9:16", 1.0) == (768, 1344)
    assert flux_graph.latent_size("16:9", 1.0) == (1344, 768)
    width, height = flux_graph.latent_size("9:16", 0.4)
    assert width % 32 == 0 and height % 32 == 0
    assert width * height >= 0.4 * 1_000_000


def test_aspect_must_be_written_as_a_ratio():
    with pytest.raises(ValueError, match="W:H"):
        flux_graph.parse_aspect("portrait")


def test_text_to_image_wiring_matches_the_official_template():
    built, params = flux_graph.build(spec(), seed=101)
    assert built["1"]["class_type"] == "UNETLoader"
    assert built["2"]["inputs"]["type"] == "flux2"
    assert built["4"]["inputs"]["text"] == "a quiet room"
    assert built["6"]["inputs"]["positive"] == ["4", 0]          # 无参考图时正向直连文本编码
    assert built["8"]["inputs"] == {"steps": 4, "width": 1024, "height": 1024}
    assert built["9"]["inputs"]["width"] == 1024
    assert built["10"]["inputs"]["noise_seed"] == 101
    assert built["11"]["inputs"]["sigmas"] == ["8", 0]
    assert built["13"]["class_type"] == "SaveImage"
    assert built["13"]["inputs"]["filename_prefix"] == "flux2/scene-room"
    assert params["width"] == 1024 and params["seed"] == 101


def test_reference_images_chain_into_the_positive_conditioning():
    built, params = flux_graph.build(spec(references=["/tmp/a.png", "/tmp/b.png"]), seed=7)
    assert [built[f"ref{i}_load"]["inputs"]["image"] for i in (0, 1)] == ["a.png", "b.png"]
    assert built["ref1_ref"]["inputs"]["conditioning"] == ["ref0_ref", 0]   # 首尾相接
    assert built["6"]["inputs"]["positive"] == ["ref1_ref", 0]             # 最后一环挂正向
    assert built["ref0_encode"]["inputs"]["vae"] == ["3", 0]
    assert params["references"] == ["/tmp/a.png", "/tmp/b.png"]
    uploads = flux_graph.uploads(spec(references=["/tmp/a.png", "/tmp/b.png"]))
    assert [(node, label) for _, node, _, label in uploads] == \
           [("ref0_load", "<参考图 1>"), ("ref1_load", "<参考图 2>")]
