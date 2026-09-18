"""H3 建图：纯函数，不联网、不落盘。"""
import json

import pytest

from t2v.engines.h3 import graph as h3_graph, official
from t2v.errors import GraphError
from t2v.paths import ROOT
from t2v.engines.h3.request import H3Request

R2V = ROOT / "workflows/h3/r2v.api.json"
T2V = ROOT / "workflows/h3/t2v.api.json"
RETIRED_CLASSES = {"H3FunControlApply", "H3FunControlLoader", "MiniMaxH3AddGuide"}


def request(**overrides):
    fields = dict(workflow=R2V, name="c001", duration=3.0, megapixels=0.4,
                  aspect="16:9 (Widescreen)", steps=20)
    fields.update(overrides)
    return H3Request(**fields)


def build(**overrides):
    seed = overrides.pop("seed_value", 20260920)
    return h3_graph.build(request(**overrides), seed)[0]


def node_of(graph, class_type):
    return next(value for value in graph.values() if value["class_type"] == class_type)


def test_sampling_parameters_land_on_the_right_nodes():
    graph = build(turbo=True)
    resolution = node_of(graph, "ResolutionSelector")["inputs"]
    assert resolution["megapixels"] == 0.4 and resolution["aspect_ratio"] == "16:9 (Widescreen)"
    assert node_of(graph, "PrimitiveFloat")["inputs"]["value"] == 3.0
    assert node_of(graph, "PrimitiveInt")["inputs"]["value"] == 20
    assert node_of(graph, "RandomNoise")["inputs"]["noise_seed"] == 20260920
    assert node_of(graph, "PrimitiveBoolean")["inputs"]["value"] is True
    assert node_of(graph, "SaveVideo")["inputs"]["filename_prefix"] == "video/c001"


def test_prompt_goes_through_the_string_node_on_the_r2v_template():
    graph = build(prompt_text="a swordswoman on still water")
    main = node_of(graph, "MiniMaxH3ReferenceToVideo")
    string_node = graph[main["inputs"]["prompt"][0]]
    assert string_node["inputs"]["value"] == "a swordswoman on still water"


def test_reference_images_use_the_canvas_node_ids(tmp_path):
    refs = []
    for index in range(4):
        path = tmp_path / f"ref{index}.png"
        path.write_bytes(b"png")
        refs.append(path)
    graph = build(refs=refs, ref_image_size="max")
    assert [h3_graph.ref_node_id(i) for i in range(4)] == ["137", "139", "922", "923"]
    main = node_of(graph, "MiniMaxH3ReferenceToVideo")
    for index, node_id in enumerate(["137", "139", "922", "923"]):
        assert graph[node_id]["class_type"] == "LoadImage"
        assert graph[node_id]["inputs"]["image"] == f"ref{index}.png"
        assert graph[node_id]["_meta"]["title"] == f"<Picture {index + 1}>"
        assert main["inputs"][f"ref_images.ref_image_{index}"] == [node_id, 0]
    assert main["inputs"]["ref_image_size"] == "max"


def test_reference_video_and_first_frame_wire_their_loaders(tmp_path):
    clip = tmp_path / "ref.mp4"
    clip.write_bytes(b"mp4")
    graph = build(ref_video=clip, ref_video_audio=True)
    main = node_of(graph, "MiniMaxH3ReferenceToVideo")
    assert graph["930"]["inputs"]["file"] == "ref.mp4"
    assert main["inputs"]["ref_videos.ref_video_0"] == ["931", 0]
    assert main["inputs"]["ref_video_audios.ref_video_audio_0"] == ["931", 1]
    with pytest.raises(GraphError, match="R2V"):
        h3_graph.build(request(workflow=T2V, ref_video=clip), 1)


def test_the_graph_carries_no_retired_control_or_guide_nodes(tmp_path):
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"png")
    graph = build(refs=[ref])
    assert RETIRED_CLASSES.isdisjoint({value["class_type"] for value in graph.values()})
    assert not any(key.startswith("control") or key == "guides"
                   for node in graph.values() for key in node["inputs"])


def test_upload_plan_covers_every_local_input(tmp_path):
    ref, clip = tmp_path / "a.png", tmp_path / "b.mp4"
    ref.write_bytes(b"png")
    clip.write_bytes(b"mp4")
    plan = h3_graph.uploads(request(refs=[ref], ref_video=clip))
    assert [(item[1], item[2]) for item in plan] == [("930", "file"), ("137", "image")]


def test_seed_is_taken_from_the_request_when_given():
    assert h3_graph.resolve_seed(request(seed=7)) == 7
    assert 0 <= h3_graph.resolve_seed(request()) <= h3_graph.SEED_MAX


def test_official_builder_matches_the_checked_in_workflow():
    assert official.build() == json.loads(R2V.read_text(encoding="utf-8"))
