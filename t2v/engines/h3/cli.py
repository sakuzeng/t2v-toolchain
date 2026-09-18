"""H3 引擎自己的命令行表面：`t2v h3 …` 与 `t2v graph h3 …`。"""
from pathlib import Path

from ...cliopts import (add_client_options, add_cost_gate, client_from_args,
                        generation_spec, quote_optional_for_project)
from ...errors import ProjectError
from ...frontmatter import strip as strip_frontmatter
from . import official, runner
from .request import H3Request


def run(args):
    if bool(args.capsule_root) != bool(args.shot_id):
        raise ProjectError("--capsule-root 与 --shot-id 必须同时提供")
    request = H3Request(
        workflow=Path(args.workflow),
        prompt_text=_prompt_text(args),
        prompt_path=Path(args.prompt_file) if args.prompt_file else None,
        project=args.project, shot=args.shot_id, name=args.name,
        megapixels=args.megapixels, aspect=args.aspect, duration=args.duration,
        steps=args.steps, seed=args.seed, turbo=args.turbo,
        refs=[Path(path) for path in args.ref_image], ref_image_size=args.ref_image_size,
        ref_video=Path(args.ref_video) if args.ref_video else None,
        ref_video_audio=args.ref_video_audio,
        first_frame=Path(args.first_frame) if args.first_frame else None,
        strip_audio=args.strip_audio,
        retime_output_frames=args.retime_output_frames, retime_fps=args.retime_fps,
        out_dir=Path(args.out) if args.out else None,
        capsule_root=Path(args.capsule_root) if args.capsule_root else None,
        export_ui=Path(args.export_ui) if args.export_ui else None,
        workflow_label=args.workflow_label, gpu_hourly=args.gpu_hourly,
    )
    if args.dry_run:
        runner.plan(request)
        if quote_optional_for_project(args.project):
            print("[generation]", generation_spec(request))
        return
    content_mode = quote_optional_for_project(args.project)
    if content_mode and not (args.execute and args.generation_confirmed):
        raise ProjectError("生成保护：先核对本次 prompt、工作流和参数并取得确认，再同时传 --execute --generation-confirmed")
    if content_mode:
        print("[confirmed]", generation_spec(request))
    runner.execute(request, client=client_from_args(args),
                   cost_confirmed=args.execute and (args.generation_confirmed if content_mode
                                                     else args.cost_confirmed))


def _prompt_text(args):
    """.md 允许带 YAML frontmatter（记 status/seed/产物等），只把正文送给模型；.txt 原样。"""
    if not args.prompt_file:
        return args.prompt or ""
    text = Path(args.prompt_file).read_text(encoding="utf-8")
    return strip_frontmatter(text) if str(args.prompt_file).endswith(".md") else text.strip()


def build_graph(args):
    official.write(args.out)


def add_arguments(sub):
    p = sub.add_parser("h3", help="直接调用 H3 引擎（临时实验/冒烟；项目镜头请用 plan/run）")
    add_client_options(p)
    p.add_argument("--workflow", required=True)
    p.add_argument("--prompt")
    p.add_argument("--prompt-file")
    p.add_argument("--megapixels", type=float)
    p.add_argument("--aspect")
    p.add_argument("--duration", type=float)
    p.add_argument("--seed", type=int)
    p.add_argument("--steps", type=int)
    p.add_argument("--turbo", action="store_true")
    p.add_argument("--strip-audio", action="store_true",
                   help="保留 H3 原始 output.mp4，另生成无音轨 picture.mp4 供评审和交付")
    p.add_argument("--retime-output-frames", type=int, help="把无音轨画面重定时为指定帧数，并输出 picture_retimed.mp4")
    p.add_argument("--retime-fps", type=float, default=24.0, help="重定时评审版帧率，默认 24")
    p.add_argument("--project", help="项目名：产物写到 projects/<项目>/outputs/")
    p.add_argument("--name", default="run")
    p.add_argument("--out", help="产物目录；默认 projects/<项目>/outputs 或 projects/smoke/outputs")
    p.add_argument("--workflow-label", help="写入画布元数据并追加到 Prompt 节点标题，便于在浏览器辨认镜头版本")
    p.add_argument("--export-ui", help="在提交或 dry-run 前导出已同步本次参数的 ComfyUI 画布 JSON")
    p.add_argument("--shot-id", help="v2 镜头稳定 ID；与 --capsule-root 一起使用")
    p.add_argument("--capsule-root", help="v2 run capsule 根目录；产物写到 <root>/<shot>/<run-id>/")
    p.add_argument("--gpu-hourly", type=float, default=0.0, help="GPU 每小时费用，仅用于 run.json 实际渲染费用估算")
    p.add_argument("--ref-image", action="append", default=[],
                   help="R2V：参考图路径，可重复；按顺序成为 <Picture 1>, <Picture 2>…")
    p.add_argument("--ref-image-size", choices=["match", "max"],
                   help="R2V 参考图尺寸：match=缩到与输出同像素面积（480p 时脸只剩几十像素）；max=2048 短边保身份，慢数倍")
    p.add_argument("--ref-video", help="R2V：参考视频路径（mp4），经 LoadVideo→GetVideoComponents 成为 <Video 1>")
    p.add_argument("--ref-video-audio", action="store_true", help="同时把参考视频音轨接到 <Audio 1>")
    p.add_argument("--first-frame", help="I2V：本地图片，上传后接到 MiniMaxH3ImageToVideo.first_frame")
    p.add_argument("--dry-run", action="store_true")
    add_cost_gate(p)
    p.set_defaults(func=run)


def add_graph_arguments(sub):
    p = sub.add_parser("h3", help="重建官方 H3 R2V 工作流")
    p.add_argument("--out", help="默认写回 workflows/h3/r2v.api.json")
    p.set_defaults(func=build_graph)
