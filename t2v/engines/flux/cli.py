"""flux 引擎自己的命令行表面：`t2v flux …` 与 `t2v graph flux …`。

`flux` 不实现项目-镜头契约（那套是 H3 的 vNNN.md 版本阶梯），它按**生图 prompt 文件**工作，
所以入口是 `t2v flux <项目> <prompt 文件>`。
"""
import json
from pathlib import Path

from ...cliopts import add_client_options, add_cost_gate, client_from_args
from ...errors import CostGuardError
from . import graph as graph_builder
from . import prompt as prompt_mod
from . import runner


def run(args):
    spec = prompt_mod.from_file(args.project, args.prompt_file,
                                {"seed": args.seed, "steps": args.steps,
                                 "megapixels": args.megapixels})
    if not args.execute:
        runner.plan(spec)
        print("[generation]", spec.describe())
        return
    if not args.generation_confirmed:
        print("[generation]", spec.describe())
        raise CostGuardError("占卡保护：确认本次出图内容后，同时传 "
                             "--execute --generation-confirmed")
    print("[confirmed]", spec.describe())
    runner.execute(spec, client=client_from_args(args), cost_confirmed=True,
                   write_target=args.write_target)


def build_graph(args):
    spec = prompt_mod.from_file(args.project, args.prompt_file,
                                {"seed": args.seed, "steps": args.steps,
                                 "megapixels": args.megapixels})
    seed = spec.seed if spec.seed is not None else 0
    graph, params = graph_builder.build(spec, seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("[graph]", out, f"（{params['width']}x{params['height']}, "
                          f"steps={params['steps']}, seed={seed}）")


def add_arguments(sub):
    p = sub.add_parser("flux", help="用 FLUX.2 [klein] 出一张图（读项目的生图 prompt）")
    p.add_argument("project", help="项目 slug")
    p.add_argument("prompt_file", help="生图 prompt 的 .md（如 prompts/scene/sofa-room/v001.md）")
    p.add_argument("--seed", type=int)
    p.add_argument("--steps", type=int)
    p.add_argument("--megapixels", type=float)
    p.add_argument("--write-target", action="store_true",
                   help="评审通过后加它：把产物同时复制到 frontmatter 的 target")
    add_client_options(p)
    add_cost_gate(p)
    p.set_defaults(func=run)


def add_graph_arguments(sub):
    p = sub.add_parser("flux", help="只建图并导出 API JSON（免费、不联网）")
    p.add_argument("project")
    p.add_argument("prompt_file")
    p.add_argument("--seed", type=int)
    p.add_argument("--steps", type=int)
    p.add_argument("--megapixels", type=float)
    p.add_argument("--out", required=True)
    p.set_defaults(func=build_graph)
