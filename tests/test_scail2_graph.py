"""SCAIL-2 建图与报价（不联网）。"""
from t2v.engines.scail2 import graph as scail2_graph, request as scail2_request


def build(mode="maskcheck", **kwargs):
    return scail2_graph.build(mode, "drive.mp4", "person.png", "", scail2_graph.NEG_DEFAULT,
                              1, 69, 864, 480, **kwargs)


def test_maskcheck_stops_after_the_mask_and_full_adds_the_sampler():
    mask_only = build()
    assert mask_only["1"]["class_type"] == "LoadVideo"
    assert mask_only["3"]["class_type"] == "LoadImage"
    assert "20" not in mask_only                      # WanSCAILToVideo 只在 full 里
    full = build("full")
    assert full["20"]["class_type"] == "WanSCAILToVideo"
    assert full["23"]["inputs"]["noise_seed"] == 1


def test_extra_reference_views_chain_through_image_batch():
    graph = build(ref_extra=["back.png", "face.png"])
    assert graph["40"]["inputs"]["image"] == "back.png"
    assert graph["50"]["inputs"]["image1"] == ["3", 0]
    assert graph["51"]["inputs"]["image1"] == ["50", 0]
    assert graph["8"]["inputs"]["images"] == ["51", 0]


def test_distillation_lora_can_be_switched_off():
    with_lora = build("full")
    assert with_lora["12"]["class_type"] == "LoraLoaderModelOnly"
    assert with_lora["13"]["inputs"]["model"] == ["12", 0]
    without = build("full", distill_strength=0.0)
    assert "12" not in without
    assert without["13"]["inputs"]["model"] == ["11", 0]


def test_quote_scales_with_length_steps_and_cfg():
    base = scail2_request.Scail2Request(project="p", exp="e", mode="full", driving="d.mp4", ref="r.png")
    slow = scail2_request.Scail2Request(project="p", exp="e", mode="full", driving="d.mp4", ref="r.png", steps=40, cfg=5.0)
    assert scail2_request.estimate_minutes(base, 69) < scail2_request.estimate_minutes(slow, 69)
    assert scail2_request.estimate_minutes(base, 69) < scail2_request.estimate_minutes(base, 141)
    mask = scail2_request.Scail2Request(project="p", exp="e", mode="maskcheck", driving="d.mp4", ref="r.png")
    assert scail2_request.estimate_minutes(mask, 69) == scail2_request.MASKCHECK_MINUTES
