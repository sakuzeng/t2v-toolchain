"""把一次 H3Request 写进官方 API 工作流。纯函数、不碰网络与磁盘产物，可单测。"""
import copy
import json
from pathlib import Path
import random

from ...comfy.graph import find, node
from ...errors import GraphError

MAIN_CLASSES = ("MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo")
R2V = "MiniMaxH3ReferenceToVideo"
SEED_MAX = 2 ** 48


def resolve_seed(request):
    """H3 没有默认 seed；没指定就随机一个并记进 run.json，方便复跑。"""
    return request.seed if request.seed is not None else random.randint(0, SEED_MAX)


def main_node(graph):
    for class_type in MAIN_CLASSES:
        if any(value["class_type"] == class_type for value in graph.values()):
            return find(graph, class_type)
    raise GraphError("图里没有 MiniMaxH3ImageToVideo / MiniMaxH3ReferenceToVideo 节点")


def ref_node_id(index):
    """前两张沿用画布模板的 137/139，便于 .ui.json 同步显示；之后顺延到 922、923…"""
    return str(137 + 2 * index) if index < 2 else str(920 + index)


def build(request, seed):
    """返回 (graph, graph0, params)：graph0 是模板原样，用于画布同步比对旧值。"""
    graph = json.loads(Path(request.workflow).read_text(encoding="utf-8"))
    graph0 = copy.deepcopy(graph)
    params = {"strip_audio": bool(request.strip_audio)}
    _, main = main_node(graph)

    if request.prompt_text:
        target = main["inputs"]["prompt"]
        if isinstance(target, list):      # prompt 来自字符串节点（R2V 模板）
            graph[target[0]]["inputs"]["value"] = request.prompt_text
        else:
            main["inputs"]["prompt"] = request.prompt_text
        params["prompt"] = request.prompt_text
    if request.megapixels is not None:
        find(graph, "ResolutionSelector")[1]["inputs"]["megapixels"] = request.megapixels
        params["megapixels"] = request.megapixels
    if request.aspect:
        find(graph, "ResolutionSelector")[1]["inputs"]["aspect_ratio"] = request.aspect
        params["aspect"] = request.aspect
    if request.duration is not None:
        find(graph, "PrimitiveFloat")[1]["inputs"]["value"] = request.duration
        params["duration"] = request.duration
    find(graph, "RandomNoise")[1]["inputs"]["noise_seed"] = seed
    params["seed"] = seed
    if request.steps is not None:
        find(graph, "PrimitiveInt")[1]["inputs"]["value"] = request.steps
        params["steps"] = request.steps
    find(graph, "PrimitiveBoolean")[1]["inputs"]["value"] = bool(request.turbo)
    params["turbo"] = bool(request.turbo)
    find(graph, "SaveVideo")[1]["inputs"]["filename_prefix"] = f"video/{request.name}"

    if request.refs:
        if main["class_type"] != R2V:
            raise GraphError("参考图需要 R2V 工作流（workflows/h3/r2v.api.json）")
        for index, path in enumerate(request.refs):
            node_id = ref_node_id(index)
            graph[node_id] = node("LoadImage", title=f"<Picture {index + 1}>", image=Path(path).name)
            main["inputs"][f"ref_images.ref_image_{index}"] = [node_id, 0]
        params["ref_images"] = [str(path) for path in request.refs]
    if request.ref_image_size:
        main["inputs"]["ref_image_size"] = request.ref_image_size
        params["ref_image_size"] = request.ref_image_size
    if request.ref_video:
        if main["class_type"] != R2V:
            raise GraphError("--ref-video 需要 R2V 工作流")
        graph["930"] = node("LoadVideo", title="<Video 1>", file=Path(request.ref_video).name)
        graph["931"] = node("GetVideoComponents", title="<Video 1> components", video=["930", 0])
        main["inputs"]["ref_videos.ref_video_0"] = ["931", 0]
        if request.ref_video_audio:
            main["inputs"]["ref_video_audios.ref_video_audio_0"] = ["931", 1]
        params["ref_video"] = str(request.ref_video)
        params["ref_video_audio"] = bool(request.ref_video_audio)
    if request.first_frame:
        graph["900"] = node("LoadImage", title="first_frame", image=Path(request.first_frame).name)
        find(graph, "MiniMaxH3ImageToVideo")[1]["inputs"]["first_frame"] = ["900", 0]
        params["first_frame"] = str(request.first_frame)
    return graph, graph0, params


def uploads(request):
    """需要先 POST /upload/image 的本机文件 → 上传后要回填的节点 id 与字段。"""
    plan = []
    if request.first_frame:
        plan.append((request.first_frame, "900", "image", "first_frame"))
    if request.ref_video:
        plan.append((request.ref_video, "930", "file", "<Video 1>"))
    for index, path in enumerate(request.refs):
        plan.append((path, ref_node_id(index), "image", f"<Picture {index + 1}>"))
    return plan
