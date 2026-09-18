"""SCAIL-2 实验执行：maskcheck（几乎免费）与 full（付费出片）。产物写进项目的 experiments/<exp>/runs/。"""
import os
from pathlib import Path
import time

from ... import paths
from ...errors import ComfyError, CostGuardError, ProjectError
from ...comfy.client import ComfyClient
from ...media import probe_video
from ...provenance import git_state, sha256_file
from ..capsule import RunCapsule
from . import graph as graph_builder
from .request import estimate_minutes

COST_GUARD = "付费保护：先 dry-run 报价并获得本轮确认，再同时传 --execute --cost-confirmed"


def prepare(request):
    """校验尺寸/帧数、建图并打印报价。不联网、不上传。"""
    if request.mode == "full" and not request.prompt_file:
        raise ProjectError("--mode full 需要 --prompt-file")
    probed = probe_video(str(request.driving))
    length = request.length or probed["frames"]
    width = request.width or probed["width"]
    height = request.height or probed["height"]
    if (length - 1) % 4:
        raise ProjectError(f"驱动片 {length} 帧不是 4n+1，请用 --length 截断")
    if width % 32 or height % 32:
        raise ProjectError(f"{width}x{height} 不是 32 的倍数，请用 --width/--height")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    prompt = Path(request.prompt_file).read_text(encoding="utf-8").strip() if request.prompt_file else ""
    negative = graph_builder.NEG_DEFAULT + (("，" + request.negative_extra) if request.negative_extra else "")
    graph = graph_builder.build(
        request.mode, Path(request.driving).name, Path(request.ref).name, prompt, negative, request.seed,
        length, width, height, request.sam3_word, request.sam3_word_ref or request.sam3_word,
        [Path(path).name for path in request.ref_extra], request.steps, request.cfg, request.distill, request.dpo,
        pose_strength=request.pose_strength, pose_end=request.pose_end, replacement=request.replacement,
        max_objects=request.max_objects, prefix=f"scail2/{request.exp}_{request.mode}_{stamp}")
    print(f"[graph] {request.mode} {len(graph)} 节点，附加视图 {len(request.ref_extra)}，"
          f"{width}x{height} x {length} 帧，steps={request.steps} cfg={request.cfg} "
          f"distill={request.distill} seed={request.seed} replacement={request.replacement}")
    minutes = estimate_minutes(request, length)
    print(f"[quote] 估算 {minutes:.1f} 分钟，约 ¥{minutes / 60 * request.gpu_hourly:.2f}"
          f"（按 ¥{request.gpu_hourly}/时；无实测基线，仅供确认用）")
    return graph, prompt, stamp, {"length": length, "width": width, "height": height, "probe": probed}


def plan(request):
    graph, _, _, _ = prepare(request)
    print("[dry-run] 未上传、未提交")
    return graph


def execute(request, client=None, cost_confirmed=False):
    if not cost_confirmed:
        raise CostGuardError(COST_GUARD)
    client = client or ComfyClient()
    graph, prompt, stamp, shape = prepare(request)

    device = client.device()
    print(f"[remote] {device['name']} free {device['vram_free'] // 2 ** 20} MiB")
    missing = client.missing_nodes({node["class_type"] for node in graph.values()})
    if missing:
        raise ComfyError(f"远端缺节点：{missing}")

    driving_upload = client.upload(str(request.driving))
    ref_upload = client.upload(str(request.ref))
    graph["1"]["inputs"]["file"] = driving_upload["name"]
    graph["3"]["inputs"]["image"] = ref_upload["name"]
    print("[upload]", driving_upload, ref_upload)
    for index, extra in enumerate(request.ref_extra):
        upload = client.upload(str(extra))
        graph[str(40 + index)]["inputs"]["image"] = upload["name"]
        print("[upload] extra", upload)

    prompt_id = client.submit(graph)
    print("[submit] prompt_id", prompt_id)
    runs_dir = request.experiment_dir / "runs"
    capsule = RunCapsule(runs_dir / f"{stamp}_{request.mode}_seed{request.seed}_{prompt_id[:8]}",
                         index_path=runs_dir / "index.jsonl")
    capsule.write_json("workflow.api.json", graph, indent=1)
    if prompt:
        capsule.write_text("prompt.md", prompt + "\n")

    started = time.time()
    try:
        entry = client.wait(prompt_id, started_at=started)
    except ComfyError as exc:
        if getattr(exc, "history", None):
            capsule.write_json("history_error.json", exc.history, indent=1)
        raise
    wall = time.time() - started
    print(f"\n[done] {wall:.0f}s")

    saved = []
    for node_id, items in client.outputs_by_node(entry):
        for index, item in enumerate(items):
            data = client.download(item)
            title = graph.get(node_id, {}).get("_meta", {}).get("title", node_id).replace(" ", "_").replace("/", "_")
            suffix = "" if len(items) == 1 else f"-{index:02d}"
            target = capsule.write_bytes(title + suffix + os.path.splitext(item["filename"])[1], data)
            saved.append(target)
            print("[saved]", target, f"{len(data) // 1024} KB")

    exec_seconds = client.exec_seconds(entry)
    sidecar = {
        "prompt_id": prompt_id, "mode": request.mode, "seed": request.seed,
        "length": shape["length"], "width": shape["width"], "height": shape["height"],
        "steps": request.steps, "cfg": request.cfg, "distill": request.distill, "dpo": request.dpo,
        "pose_strength": request.pose_strength, "pose_end": request.pose_end, "replacement": request.replacement,
        "negative_extra": request.negative_extra, "max_objects": request.max_objects,
        "sam3_word": request.sam3_word, "sam3_word_ref": request.sam3_word_ref or request.sam3_word,
        "device": device["name"], "wall_seconds": round(wall, 1), "exec_seconds": exec_seconds,
        "estimated_render_cost": round((exec_seconds or wall) / 3600 * request.gpu_hourly, 4),
        "gpu_hourly": request.gpu_hourly,
        "inputs": {
            "driving": {"path": _relative(request.driving), "sha256": sha256_file(str(request.driving)),
                        **shape["probe"]},
            "ref": {"path": _relative(request.ref), "sha256": sha256_file(str(request.ref))},
            "ref_extra": [{"path": _relative(path), "sha256": sha256_file(str(path))} for path in request.ref_extra],
        },
        "outputs": [_relative(path) for path in saved], "git": git_state(), "submitted_at": stamp,
    }
    capsule.write_json("run.json", sidecar, indent=1)
    capsule.append_index(sidecar)
    print("[sidecar]", capsule.path("run.json"), "exec_seconds", exec_seconds)
    return sidecar


def _relative(path):
    return os.path.relpath(str(path), str(paths.ROOT))
