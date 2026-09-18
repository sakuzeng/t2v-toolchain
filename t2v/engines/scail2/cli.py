"""SCAIL-2 引擎自己的命令行表面：`t2v scail2 …` 与 `t2v graph scail2 …`。"""
import json
from pathlib import Path

from ...cliopts import add_client_options, add_cost_gate, client_from_args
from ...errors import ProjectError
from . import graph as graph_builder, runner
from .request import Scail2Request


def run(args):
    request = Scail2Request(
        project=args.project, exp=args.exp, mode=args.mode,
        driving=Path(args.driving), ref=Path(args.ref),
        ref_extra=[Path(path) for path in args.ref_extra],
        prompt_file=Path(args.prompt_file) if args.prompt_file else None,
        seed=args.seed, length=args.length, width=args.width, height=args.height,
        sam3_word=args.sam3_word, sam3_word_ref=args.sam3_word_ref,
        steps=args.steps, cfg=args.cfg, distill=args.distill, dpo=args.dpo,
        pose_strength=args.pose_strength, pose_end=args.pose_end, animation=args.animation,
        negative_extra=args.negative_extra, max_objects=args.max_objects, gpu_hourly=args.gpu_hourly,
    )
    if args.dry_run:
        runner.plan(request)
        return
    runner.execute(request, client=client_from_args(args),
                   cost_confirmed=args.execute and args.cost_confirmed)


def build_graph(args):
    if (args.length - 1) % 4:
        raise ProjectError(f"length 必须是 4n+1，当前 {args.length}")
    if args.width % 32 or args.height % 32:
        raise ProjectError("宽高必须是 32 的倍数")
    prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip() if args.prompt_file else ""
    graph = graph_builder.build(
        args.mode, args.driving, args.ref, prompt, args.negative, args.seed, args.length, args.width, args.height,
        args.sam3_word, args.sam3_word_ref or args.sam3_word, args.ref_extra, args.steps, args.cfg,
        args.distill, args.dpo, pose_strength=args.pose_strength, pose_end=args.pose_end,
        replacement=not args.animation, prefix=args.prefix)
    with open(args.out, "w", encoding="utf-8") as stream:
        json.dump(graph, stream, ensure_ascii=False, indent=1)
    print(f"[graph] {args.mode}: {len(graph)} 节点 -> {args.out}")


def _add_shared_arguments(p):
    """提交与建图共用的部分。mode/seed/尺寸两边默认值不同（提交时从驱动片探测，建图时写死），各自声明。"""
    p.add_argument("--driving", required=True)
    p.add_argument("--ref", required=True)
    p.add_argument("--ref-extra", action="append", default=[], help="附加参考视图（可重复）")
    p.add_argument("--prompt-file")
    p.add_argument("--sam3-word", default="human")
    p.add_argument("--sam3-word-ref", default=None)
    p.add_argument("--steps", type=int, default=6)
    p.add_argument("--cfg", type=float, default=1.0)
    p.add_argument("--distill", type=float, default=0.8)
    p.add_argument("--dpo", type=float, default=1.0)
    p.add_argument("--pose-strength", type=float, default=1.0)
    p.add_argument("--pose-end", type=float, default=1.0)
    p.add_argument("--animation", action="store_true", help="动画模式（默认替换模式）")


def add_arguments(sub):
    p = sub.add_parser("scail2", help="SCAIL-2 角色替换实验")
    add_client_options(p)
    p.add_argument("--project", required=True)
    p.add_argument("--exp", required=True)
    p.add_argument("--mode", choices=("maskcheck", "full"), required=True)
    _add_shared_arguments(p)
    p.add_argument("--seed", type=int, default=20260908)
    p.add_argument("--length", type=int, default=None, help="默认取驱动视频帧数")
    p.add_argument("--width", type=int, default=None)
    p.add_argument("--height", type=int, default=None)
    p.add_argument("--negative-extra", default="", help="追加到默认负向词之后（CFG>1 时才有效）")
    p.add_argument("--max-objects", type=int, default=1, help="SAM3 最多跟踪身份数")
    p.add_argument("--gpu-hourly", type=float, default=2.78)
    p.add_argument("--dry-run", action="store_true")
    add_cost_gate(p)
    p.set_defaults(func=run)


def add_graph_arguments(sub):
    p = sub.add_parser("scail2", help="展开 SCAIL-2 官方模板为无子图 API 工作流")
    p.add_argument("--mode", choices=("maskcheck", "full"), default="full")
    _add_shared_arguments(p)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--length", type=int, default=69)
    p.add_argument("--width", type=int, default=864)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--negative", default=graph_builder.NEG_DEFAULT)
    p.add_argument("--prefix", default="scail2/run")
    p.add_argument("--out", required=True)
    p.set_defaults(func=build_graph)
