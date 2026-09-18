"""H3 的执行侧：报价/建图（免费）与提交—轮询—下载—记账（付费）。"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, Optional

from ... import paths
from ...comfy.client import ComfyClient, remote_name
from ...comfy.graph import find, synced_ui_workflow
from ...errors import CostGuardError, GraphError
from ...media import retime_video
from ...provenance import git_state, input_record
from ..capsule import RunCapsule
from . import graph as graph_builder

COST_GUARD = "付费保护：提交前须按项目确认策略取得本轮用户确认；默认先 dry-run 报价并确认，再传 --execute --cost-confirmed"


@dataclass
class Prepared:
    """建好的图与本次参数；dry-run 到此为止，执行时接着用。"""
    request: Any
    seed: int
    graph: Dict[str, Any]
    params: Dict[str, Any]
    ui: Optional[Dict[str, Any]]


def prepare(request):
    seed = graph_builder.resolve_seed(request)
    graph, graph0, params = graph_builder.build(request, seed)
    resolution = find(graph, "ResolutionSelector")[1]["inputs"]
    print(f"[plan] {request.name}: {resolution['aspect_ratio']} @ {resolution['megapixels']}MP, "
          f"duration={find(graph, 'PrimitiveFloat')[1]['inputs']['value']}s, "
          f"steps={find(graph, 'PrimitiveInt')[1]['inputs']['value']}, "
          f"turbo={params['turbo']}, seed={seed}")
    if request.duration is not None:
        print(f"[plan] 帧数 {request.frames}（24 fps 的 17k+5 桶）")
    preview = (request.prompt_text or str(graph_builder.main_node(graph)[1]["inputs"]["prompt"]))[:120]
    print("[plan] prompt:", preview.replace("\n", " "), "…")
    ui = synced_ui_workflow(request.workflow, graph0, graph, request.workflow_label)
    if request.export_ui:
        if not ui:
            raise GraphError("--export-ui 需要与 API 工作流同名的 .ui.json 模板")
        export = Path(request.export_ui)
        export.parent.mkdir(parents=True, exist_ok=True)
        with export.open("w", encoding="utf-8") as stream:
            json.dump(ui, stream, indent=1, ensure_ascii=False)
        print("[ui]", export, "（已同步本次参数，可拖入浏览器画布）")
    return Prepared(request=request, seed=seed, graph=graph, params=params, ui=ui)


def plan(request):
    prepared = prepare(request)
    print("[dry-run] 未提交")
    return prepared


def execute(request, client=None, cost_confirmed=False, client_id="auto"):
    """提交一次真实生成。调用方按项目策略取得本轮用户确认后才可传入确认标记。"""
    if not cost_confirmed:
        raise CostGuardError(COST_GUARD)
    client = client or ComfyClient()
    prepared = prepare(request)
    graph, params, ui = prepared.graph, prepared.params, prepared.ui

    inputs = [input_record(path) for path in _provenance_paths(request)]
    session = client.browser_client_id(client_id)
    device = client.device()
    print(f"[remote] {device['name']} free {device['vram_free'] // 2 ** 20} MiB")
    for path, node_id, field, label in graph_builder.uploads(request):
        upload = client.upload(path)
        print(f"[upload] {label}", upload)
        graph[node_id]["inputs"][field] = remote_name(upload)

    started = time.time()
    extra = {"extra_pnginfo": {"workflow": ui}} if ui else None
    prompt_id = client.submit(graph, client_id=session, extra_data=extra)
    print("[submit] prompt_id", prompt_id)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_id = f"{stamp}_seed{prepared.seed}_{prompt_id[:8]}"
    capsule, out_dir = _open_capsule(request, graph, run_id, stamp, prompt_id, params, inputs)
    if ui:
        name = "workflow.ui.json" if request.capsule else f"{request.name}__{stamp}__{prompt_id[:8]}.ui.json"
        with (out_dir / name).open("w", encoding="utf-8") as stream:
            json.dump(ui, stream, ensure_ascii=False)
        print("[ui]", out_dir / name, "（可拖进画布查看，含本次参数）")

    entry = client.wait(prompt_id, started_at=started)
    wall = time.time() - started
    print(f"\n[done] {wall:.0f}s")

    remote_files = client.outputs(entry)
    saved = _save_outputs(client, remote_files, out_dir, request, stamp, prompt_id)
    saved += _post_process(request, saved, out_dir, stamp, prompt_id, params)
    _probe_first_video(saved, params)
    # 实际像素要到下载后 ffprobe 才知道，而 capsule 在提交时就建好了；
    # 这里补一次改名，让目录名自带分辨率，挑片时不必逐个翻 run.json。
    run_id, out_dir, saved = _name_with_resolution(capsule, run_id, out_dir, saved, params)

    exec_seconds = client.exec_seconds(entry)
    estimated = round((exec_seconds or wall) * request.gpu_hourly / 3600, 4) if request.gpu_hourly else None
    sidecar = {
        "schema_version": 2 if request.capsule else 1,
        "run_id": run_id if request.capsule else None,
        "project": request.project, "shot": request.shot, "name": request.name, "prompt_id": prompt_id,
        "workflow": str(request.workflow), "params": params, "inputs": inputs, "git": git_state(),
        "wall_seconds": round(wall, 1), "exec_seconds": exec_seconds, "gpu_hourly": request.gpu_hourly,
        "estimated_render_cost": estimated,
        "remote_files": remote_files, "saved": [str(path) for path in saved],
        "submitted_at": stamp, "device": device["name"],
    }
    sidecar_name = "run.json" if request.capsule else f"{request.name}__{stamp}__{prompt_id[:8]}.json"
    with (out_dir / sidecar_name).open("w", encoding="utf-8") as stream:
        json.dump(sidecar, stream, indent=1, ensure_ascii=False)
    print("[sidecar]", out_dir / sidecar_name, "exec_seconds", exec_seconds)
    if capsule:
        capsule.write_json(os.path.join("logs", "comfy-status.json"), entry.get("status", {}), indent=1)
        row = {key: sidecar[key] for key in (
            "run_id", "project", "shot", "prompt_id", "submitted_at", "device", "exec_seconds",
            "estimated_render_cost")}
        # 挑片时要按分辨率/时长筛，不该逼人逐个翻 run.json。
        # 用 ffprobe 实测的像素而不是 megapixels——ResolutionSelector 算出的实际尺寸
        # 与「√(MP·比例) 取 32 倍数」的估算不一致（docs/ops/BASELINE.md #7）。
        video = params.get("video") or {}
        row["resolution"] = f"{video['width']}x{video['height']}" if video else None
        row["frames"] = video.get("frames")
        row["duration"] = params.get("duration")
        row["seed"] = params.get("seed")
        index = capsule.append_index(row)
        print("[index]", index)
    return sidecar


def _name_with_resolution(capsule, run_id, out_dir, saved, params):
    """把 run capsule 目录改名为 <时间戳>_<宽x高>_seed<seed>_<prompt-id>。

    用 ffprobe 实测像素而不是 megapixels：ResolutionSelector 的实际结果与
    「√(MP·比例) 取 32 倍数」的手算对不上（docs/ops/BASELINE.md #7）。
    探测失败或目标已存在时保持原名，不影响本次产物。
    """
    video = params.get("video")
    if not capsule or not video:
        return run_id, out_dir, saved
    stamp, _, rest = run_id.partition("_")
    new_id = f"{stamp}_{video['width']}x{video['height']}_{rest}"
    target = out_dir.parent / new_id
    if target.exists():
        print("[rename] 跳过：目标已存在", target)
        return run_id, out_dir, saved
    try:
        out_dir.rename(target)
    except OSError as exc:
        print("[rename] 跳过：", exc)
        return run_id, out_dir, saved
    capsule.dir = target
    saved = [target / path.name for path in saved]
    # request.json 在提交时就写好了，带的是改名前的 id；同步它，免得同一 capsule 里两个 id 打架。
    req_path = target / "request.json"
    if req_path.is_file():
        try:
            data = json.loads(req_path.read_text(encoding="utf-8"))
            data["run_id"] = new_id
            req_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except (OSError, ValueError) as exc:
            print("[rename] request.json 同步失败：", exc)
    print("[rename]", new_id, "（目录名自带分辨率）")
    return new_id, target, saved


def _provenance_paths(request):
    found = [request.workflow]
    if request.prompt_path:
        found.append(request.prompt_path)
    found += list(request.refs)
    found += [path for path in (request.ref_video, request.first_frame) if path]
    return [str(path) for path in found]


def _open_capsule(request, graph, run_id, stamp, prompt_id, params, inputs):
    if not request.capsule:
        out_dir = Path(request.out_dir or paths.ROOT / "projects" / (request.project or "smoke") / "outputs")
        out_dir.mkdir(parents=True, exist_ok=True)
        return None, out_dir
    capsule = RunCapsule(Path(request.capsule_root) / request.shot / run_id,
                         index_path=Path(request.capsule_root) / "index.jsonl",
                         subdirs=("logs", "qa"))
    capsule.write_json("request.json", {
        "schema_version": 2, "project": request.project, "shot": request.shot, "run_id": run_id,
        "prompt_id": prompt_id, "params": params, "inputs": inputs,
        "submitted_at": stamp, "command": sys.argv, "git": git_state(),
    })
    capsule.write_text("prompt.md", Path(request.prompt_path).read_text(encoding="utf-8")
                       if request.prompt_path else (request.prompt_text or ""))
    capsule.write_json("workflow.api.json", graph, indent=1)   # 冻结实际提交的图，含上传后的远端文件名
    return capsule, capsule.dir


def _save_outputs(client, remote_files, out_dir, request, stamp, prompt_id):
    saved, counts = [], {}
    for item in remote_files:
        data = client.download(item)
        extension = os.path.splitext(item["filename"])[1] or ".mp4"
        counts[extension] = counts.get(extension, 0) + 1
        suffix = "" if counts[extension] == 1 else f"-{counts[extension]:02d}"
        base = "output" if request.capsule else f"{request.name}__{stamp}__{prompt_id[:8]}"
        target = out_dir / (base + suffix + extension)
        target.write_bytes(data)
        saved.append(target)
        print("[saved]", target, f"{len(data) // 1024} KB")
    return saved


def _post_process(request, saved, out_dir, stamp, prompt_id, params):
    """H3 出片自带立体声；评审与交付用无音轨画面母版，必要时再重定时成对照版。"""
    extra = []
    raw = next((path for path in saved if str(path).endswith(".mp4")), None)
    picture = None
    stem = "picture" if request.capsule else f"{request.name}__{stamp}__{prompt_id[:8]}__picture"
    if request.strip_audio and raw:
        picture = out_dir / f"{stem}.mp4"
        try:
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-map", "0:v:0",
                            "-c:v", "copy", "-an", str(picture)], check=True, timeout=120)
            extra.append(picture)
            params["picture_master"] = str(picture)
            print("[picture]", picture, "（无音轨，视频流未重编码）")
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            print("[warn] 无音轨 picture master 生成失败：", exc)
            picture = None
    if request.retime_output_frames:
        source = picture or raw
        if not source or not os.path.isfile(str(source)):
            print("[warn] 重定时跳过：没有可用的视频画面母版")
        else:
            retimed = out_dir / f"{stem}_retimed.mp4"
            try:
                params["retime"] = retime_video(str(source), str(retimed),
                                                request.retime_output_frames, request.retime_fps)
                extra.append(retimed)
                print("[retime]", retimed, f"（{request.retime_output_frames} 帧 / {request.retime_fps:g} fps，无音轨）")
            except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError,
                    subprocess.TimeoutExpired) as exc:
                print("[warn] picture_retimed.mp4 生成失败：", exc)
    return extra


def _probe_first_video(saved, params):
    """实际分辨率/帧数写进 sidecar（本机需有 ffprobe；没有就跳过）。"""
    for path in saved:
        if not str(path).endswith(".mp4"):
            continue
        try:
            out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                  "-show_entries", "stream=width,height,nb_frames", "-of", "csv=p=0", str(path)],
                                 capture_output=True, text=True, timeout=30).stdout.strip().split(",")
            params.setdefault("video", {"width": int(out[0]), "height": int(out[1]), "frames": int(out[2])})
            print(f"[video] {out[0]}x{out[1]}, {out[2]} frames")
        except Exception as exc:
            print("[video] ffprobe 跳过：", exc)
