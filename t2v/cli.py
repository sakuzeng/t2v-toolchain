"""唯一命令行入口：`python3 -m t2v <命令>`。

这里只有**项目级命令**与装配：引擎的子命令由各引擎自己注册（见 `t2v/engines/__init__.py` 的契约），
`plan` / `run` 按 `project.json` 的 `engine.name` 分发，不写死任何引擎。

免费命令：validate / plan / graph / motion / contact-sheet，以及引擎的 --dry-run。
生成命令保留显式确认闸门；各项目可选择报价确认或生成内容确认。
"""
import argparse
import sys

from . import engines, migration, project as project_mod, runs as runs_mod
from .cliopts import (add_client_options, add_cost_gate, add_resolve_options,
                      client_from_args, generation_spec, quote_optional)
from .errors import ProjectError, T2VError

CONFIRM_HINT = "[next] 向用户展示以上报价并获得明确确认后，才可运行 run --execute --cost-confirmed。"
RUN_GUARD = "付费保护：先执行 plan 并取得用户确认，再同时传 --execute --cost-confirmed"
GENERATION_HINT = "[next] 核对本次 prompt、工作流、参数和参考资产，获得明确确认后运行 run --execute --generation-confirmed。报价可用 plan --quote 单独查看。"
GENERATION_GUARD = "生成保护：先核对本次 prompt、工作流、参数和参考资产并取得确认，再同时传 --execute --generation-confirmed"


# ---------- 引擎分发 ----------

def project_engine(slug):
    """按 project.json 的 engine.name 取引擎；缺省 h3（历史项目没写这个字段）。"""
    _, config = project_mod.project_context(slug)
    name = config.get("engine", {}).get("name", engines.DEFAULT)
    engine = engines.get(name)
    if not engines.supports_project_shots(engine):
        raise ProjectError(
            f"引擎 {name} 不支持项目-镜头工作流（没有 prompts/shots/<镜头>/vNNN.md 那一层）；"
            f"请直接用 python3 -m t2v {name} …")
    return engine


def _check(engine, request, stage):
    errors, warnings = engine.validate(request)
    for warning in warnings:
        print("[warn]", warning)
    if errors:
        for error in errors:
            print("[error]", error)
        raise ProjectError(f"{stage} 已停止：输入校验失败（{len(errors)} 个错误）")


# ---------- 项目命令 ----------

def cmd_init(args):
    print(f"[init] 已创建 {project_mod.init_project(args.slug, args.title)}")


def cmd_validate(args):
    project, config = project_mod.project_context(args.project)
    engine = project_engine(args.project)
    shots = [args.shot] if args.shot else project_mod.shot_ids(project, config)
    if not shots:
        raise ProjectError("没有找到可验证的镜头；请指定 shot 或创建 prompts/shots/<shot>/vNNN.md")
    errors, warnings = [], []
    for shot in shots:
        shot_errors, shot_warnings = engine.validate(engine.from_project(args.project, shot, args))
        errors += shot_errors
        warnings += shot_warnings
        print(f"[validate] {shot}: {'FAIL' if shot_errors else 'OK'}")
    for warning in warnings:
        print("[warn]", warning)
    for error in errors:
        print("[error]", error)
    if errors:
        raise ProjectError(f"验证失败：{len(errors)} 个错误，{len(warnings)} 个警告")
    print(f"[validate] 通过：{len(shots)} 个镜头，{len(warnings)} 个警告")


def cmd_plan(args):
    engine = project_engine(args.project)
    request = engine.from_project(args.project, args.shot, args)
    _check(engine, request, "plan")
    engine.plan(request)
    if quote_optional(request.config):
        print("[generation]", generation_spec(request))
        if args.quote:
            print("[quote]", engine.quote(request))
        print(GENERATION_HINT)
    else:
        print("[quote]", engine.quote(request))
        print(CONFIRM_HINT)


def cmd_run(args):
    engine = project_engine(args.project)
    request = engine.from_project(args.project, args.shot, args)
    if quote_optional(request.config):
        if not args.execute or not args.generation_confirmed:
            raise ProjectError(GENERATION_GUARD)
    elif not args.execute or not args.cost_confirmed:
        raise ProjectError(RUN_GUARD)
    if request.meta.get("do_not_generate"):
        note = request.meta.get("review_note", "该 prompt 已被标记为禁止生成")
        raise ProjectError(f"run 已停止：do_not_generate=true；{note}")
    _check(engine, request, "run")
    print("[confirmed]", generation_spec(request) if quote_optional(request.config)
          else engine.quote(request))
    engine.execute(request, client=client_from_args(args), cost_confirmed=True)


def cmd_review(args):
    project, config = project_mod.project_context(args.project)
    print("[review]", runs_mod.write_review(project, config, args.project, args.shot, args.run_id, args.force))


def cmd_promote(args):
    project, config = project_mod.project_context(args.project)
    print("[promote]", runs_mod.promote_run(project, config, args.project, args.shot,
                                            args.run_id, args.tier, args.force))


def cmd_pack(args):
    project, config = project_mod.project_context(args.project)
    dest = runs_mod.pack_project(project, config, args.project, args.out, args.include_runs)
    print(f"[pack] {dest} ({dest.stat().st_size / 1024 / 1024:.1f} MiB)")


def cmd_migrate(args):
    migration.migrate(args.project, args.execute, args.force)


# ---------- 分析 ----------

def cmd_motion(args):
    from .analysis import motion
    motion.run(args)


def cmd_contact_sheet(args):
    from .analysis import contact_sheet
    contact_sheet.run(args)


# ---------- 装配 ----------

def build_parser():
    parser = argparse.ArgumentParser(prog="t2v", description="文生视频项目、运行与交付管理（引擎可插拔）")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="从 v2 模板创建项目")
    p.add_argument("slug")
    p.add_argument("--title")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("validate", help="验证配置、prompt 和输入（免费）")
    p.add_argument("project")
    p.add_argument("shot", nargs="?")
    add_resolve_options(p)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("plan", help="免费 dry-run；报价可按项目设置为可选")
    p.add_argument("project")
    p.add_argument("shot")
    add_resolve_options(p)
    p.add_argument("--quote", action="store_true", help="内容确认项目可选显示报价")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("run", help="按项目确认策略执行生成")
    p.add_argument("project")
    p.add_argument("shot")
    add_resolve_options(p)
    add_client_options(p)
    add_cost_gate(p)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("review", help="为某次 run 建立六审表")
    p.add_argument("project")
    p.add_argument("shot")
    p.add_argument("--run-id")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("promote", help="复制选定 run 到交付区")
    p.add_argument("project")
    p.add_argument("shot")
    p.add_argument("--run-id")
    p.add_argument("--tier", choices=("preview", "master"), default="preview")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_promote)

    p = sub.add_parser("pack", help="打包可迁移项目资料")
    p.add_argument("project")
    p.add_argument("--out")
    p.add_argument("--include-runs", action="store_true")
    p.set_defaults(func=cmd_pack)

    p = sub.add_parser("migrate-v1", help="把 v1 项目按 v2 布局复制一份（不删旧文件）")
    p.add_argument("project")
    p.add_argument("--execute", action="store_true", help="执行复制；默认仅 dry-run")
    p.add_argument("--force", action="store_true", help="覆盖已存在的迁移副本")
    p.set_defaults(func=cmd_migrate)

    # 引擎自己注册 `t2v <engine>` 与 `t2v graph <engine>`
    loaded = engines.load_all()
    for engine in loaded:
        engine.add_arguments(sub)
    graph = sub.add_parser("graph", help="重建工作流 API JSON（免费，不联网）")
    graph_sub = graph.add_subparsers(dest="engine", required=True)
    for engine in loaded:
        engine.add_graph_arguments(graph_sub)

    p = sub.add_parser("motion", help="参考片运镜/停顿量化（需 OpenCV）")
    from .analysis import motion
    motion.add_arguments(p)
    p.set_defaults(func=cmd_motion)

    p = sub.add_parser("contact-sheet", help="产物 vs 参考片并排接触表（需 OpenCV）")
    from .analysis import contact_sheet
    contact_sheet.add_arguments(p)
    p.set_defaults(func=cmd_contact_sheet)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except T2VError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n[abort] 已中断", file=sys.stderr)
        return 130
    return 0
