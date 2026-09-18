"""引擎注册表。

每个引擎是 `t2v/engines/<name>/` 一个子包，自己拥有请求类型、建图、执行与命令行表面。
加一个引擎 = 新建目录 + 在 REGISTRY 加一行，不需要改 `cli.py` 或任何顶层模块。

**通用契约**（所有引擎必须导出）：
    NAME                      与 REGISTRY 的键一致，也是 project.json 里 engine.name 的取值
    add_arguments(sub)        注册 `t2v <NAME> …` 子命令，并 set_defaults(func=…)
    add_graph_arguments(sub)  注册 `t2v graph <NAME> …` 子命令

**项目-镜头契约**（支持 `t2v plan/run <项目> <镜头>` 的引擎才导出）：
    from_project(slug, shot, overrides) -> request   请求对象需带 .meta（prompt frontmatter）
    validate(request) -> (errors, warnings)
    quote(request) -> str                            免费报价文案
    plan(request)                                    免费：建图、导出画布、打印计划
    execute(request, client, cost_confirmed)         付费：提交、轮询、下载、记账

不实现项目侧契约的引擎（如 SCAIL-2）由 `cli` 给出明确提示，而不是崩在 AttributeError。
"""
import importlib

from ..errors import ProjectError

REGISTRY = {
    "h3": "t2v.engines.h3",
    "flux": "t2v.engines.flux",
    "scail2": "t2v.engines.scail2",
}
DEFAULT = "h3"
PROJECT_HOOKS = ("from_project", "validate", "quote", "plan", "execute")


def names():
    return sorted(REGISTRY)


def get(name):
    if name not in REGISTRY:
        raise ProjectError(f"未知引擎 {name!r}；可用：{', '.join(names())}")
    return importlib.import_module(REGISTRY[name])


def load_all():
    """按名字顺序返回全部引擎模块，供 CLI 装配子命令。"""
    return [get(name) for name in names()]


def supports_project_shots(engine):
    return all(hasattr(engine, hook) for hook in PROJECT_HOOKS)
