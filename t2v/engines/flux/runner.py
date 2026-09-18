"""FLUX.2 [klein] 的执行侧：plan（免费）与 execute（占卡）。

比 H3 简单：没有时长/帧数、没有音频、没有重定时与 ffprobe，产物就是一张 PNG。
产物同样落不可覆盖的 run capsule：`runs/<图片 id>/<时间戳>_seed<种子>_<prompt id>/`。
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Dict, Optional

from ... import paths
from ...comfy.client import ComfyClient, remote_name
from ...errors import CostGuardError
from ...provenance import git_state, input_record
from ..capsule import RunCapsule
from . import graph as graph_builder
from .prompt import ImageSpec, validate

COST_GUARD = ("占卡保护：提交前须与用户确认本次出图的 prompt 版本、模型与参考图，"
              "确认后同时传 --execute --generation-confirmed")


@dataclass
class Prepared:
    spec: ImageSpec
    seed: int
    graph: Dict[str, Any]
    params: Dict[str, Any]


def prepare(spec: ImageSpec) -> Prepared:
    errors, warnings = validate(spec)
    for warning in warnings:
        print("[warn]", warning)
    if errors:
        for error in errors:
            print("[error]", error)
        raise CostGuardError(f"出图已停止：输入校验失败（{len(errors)} 个错误）")
    seed = graph_builder.resolve_seed(spec)
    graph, params = graph_builder.build(spec, seed)
    print(f"[plan] {spec.image_id}: {params['width']}x{params['height']} "
          f"({spec.aspect} @ {spec.megapixels}MP), steps={spec.steps}, cfg={spec.cfg}, seed={seed}")
    print(f"[plan] unet={spec.unet} clip={spec.clip} vae={spec.vae}")
    print("[plan] prompt:", spec.prompt_text[:120].replace("\n", " "), "…")
    if spec.references:
        for index, path in enumerate(spec.references):
            print(f"[plan] <参考图 {index + 1}> {path}")
    if spec.target:
        print(f"[plan] 评审通过后要落的正式路径：{spec.target}")
    return Prepared(spec=spec, seed=seed, graph=graph, params=params)


def plan(spec: ImageSpec) -> Prepared:
    prepared = prepare(spec)
    print("[dry-run] 未提交")
    return prepared


def execute(spec: ImageSpec, client=None, cost_confirmed: bool = False,
            write_target: bool = False) -> Dict[str, Any]:
    if not cost_confirmed:
        raise CostGuardError(COST_GUARD)
    client = client or ComfyClient()
    prepared = prepare(spec)
    graph, params = prepared.graph, prepared.params

    inputs = [input_record(str(spec.prompt_path))]
    inputs += [input_record(str(path)) for path in spec.references]
    session = client.browser_client_id("auto")
    device = client.device()
    print(f"[remote] {device['name']} free {device['vram_free'] // 2 ** 20} MiB")
    for path, node_id, field, label in graph_builder.uploads(spec):
        upload = client.upload(path)
        print(f"[upload] {label}", upload)
        graph[node_id]["inputs"][field] = remote_name(upload)

    started = time.time()
    prompt_id = client.submit(graph, client_id=session)
    print("[submit] prompt_id", prompt_id)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_id = f"{stamp}_seed{prepared.seed}_{prompt_id[:8]}"
    capsule_root = Path(_runs_dir(spec.project))
    capsule = RunCapsule(capsule_root / spec.image_id / run_id,
                         index_path=capsule_root / "index.jsonl", subdirs=("logs", "qa"))
    capsule.write_json("request.json", {
        "schema_version": 2, "project": spec.project, "image": spec.image_id, "run_id": run_id,
        "prompt_id": prompt_id, "params": params, "inputs": inputs,
        "submitted_at": stamp, "command": sys.argv, "git": git_state(),
    })
    capsule.write_text("prompt.md", spec.prompt_path.read_text(encoding="utf-8"))
    capsule.write_json("workflow.api.json", graph, indent=1)

    entry = client.wait(prompt_id, started_at=started)
    wall = time.time() - started
    print(f"\n[done] {wall:.0f}s")

    saved = _save_outputs(client, client.outputs(entry), capsule.dir)
    if capsule:
        capsule.write_json(os.path.join("logs", "comfy-status.json"), entry.get("status", {}), indent=1)

    exec_seconds = client.exec_seconds(entry)
    gpu_hourly = _gpu_hourly(spec)
    estimated = round((exec_seconds or wall) * gpu_hourly / 3600, 4) if gpu_hourly else None
    sidecar = {
        "schema_version": 2, "run_id": run_id, "project": spec.project, "image": spec.image_id,
        "prompt_id": prompt_id, "params": params, "inputs": inputs, "git": git_state(),
        "wall_seconds": round(wall, 1), "exec_seconds": exec_seconds, "gpu_hourly": gpu_hourly,
        "estimated_render_cost": estimated, "saved": [str(path) for path in saved],
        "submitted_at": stamp, "device": device["name"],
    }
    if write_target and spec.target and saved:
        spec.target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(saved[0], spec.target)
        sidecar["promoted_to"] = str(spec.target)
        print("[promote]", spec.target)
    capsule.write_json("run.json", sidecar, indent=1)
    row = {key: sidecar[key] for key in ("run_id", "project", "image", "prompt_id", "submitted_at",
                                         "device", "exec_seconds", "estimated_render_cost")}
    row["resolution"] = f"{params['width']}x{params['height']}"
    row["steps"] = params["steps"]
    row["seed"] = params["seed"]
    row["output"] = str(saved[0].relative_to(capsule.dir)) if saved else None
    print("[index]", capsule.append_index(row))
    return sidecar


def _runs_dir(slug: str) -> Path:
    """项目的 runs 目录：跟 project.json 的 paths 走，而不是硬拼 ROOT/projects。"""
    from ...project import project_context, project_path
    project, config = project_context(slug)
    return project_path(project, config, "runs", "runs")


def _gpu_hourly(spec: ImageSpec) -> float:
    """项目没配 gpu_hourly 就不编数字（实验室机器本来也不按小时计费）。"""
    try:
        from ...project import project_context
        _, config = project_context(spec.project)
        return float(config.get("cost", {}).get("gpu_hourly", 0.0) or 0.0)
    except Exception:                              # noqa: BLE001 - 报价不算关键路径
        return 0.0


def _save_outputs(client, remote_files, out_dir: Path):
    saved, counts = [], {}
    for item in remote_files:
        data = client.download(item)
        extension = os.path.splitext(item["filename"])[1] or ".png"
        counts[extension] = counts.get(extension, 0) + 1
        suffix = "" if counts[extension] == 1 else f"-{counts[extension]:02d}"
        target = out_dir / f"output{suffix}{extension}"
        target.write_bytes(data)
        saved.append(target)
        print("[saved]", target, f"{len(data) // 1024} KB")
    return saved
