"""引擎与项目命令共用的 argparse 片段和项目确认方式。"""
from .comfy.client import ComfyClient, DEFAULT_BASE
from . import paths
from .project import project_context


def add_resolve_options(parser):
    """镜头级临时覆盖；不写回 prompt，只影响本次。"""
    parser.add_argument("--version", help="指定 prompt 版本，如 v021；默认取最新")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--megapixels", type=float)
    parser.add_argument("--aspect")
    parser.add_argument("--steps", type=int)
    parser.add_argument("--seed", type=int)


def add_client_options(parser):
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--poll", type=float, default=5.0)
    parser.add_argument("--client-id", default="auto",
                        help="提交时冒用的浏览器会话 id：auto=从历史里最近一次浏览器提交的任务取"
                             "（画布会实时显示进度和视频）；none=不冒用")


def add_cost_gate(parser):
    """提交保护：项目配置决定本次确认的是报价还是生成内容。"""
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--cost-confirmed", action="store_true")
    parser.add_argument("--generation-confirmed", action="store_true",
                        help="已与用户确认本次跑的 prompt 版本与工作流")


def quote_optional(config):
    """报价默认可选：每次都算报价太费时间，要看用 plan --quote 单独查。

    提交前真正必须的是跟用户确认「跑的哪个 prompt、用的什么工作流」。
    个别项目若想恢复强制报价，在 project.json 写
    generation_confirmation.quote = "required"。
    """
    return config.get("generation_confirmation", {}).get("quote") != "required"


def quote_optional_for_project(slug):
    """直接调用引擎时同样默认可选；取不到项目配置也按默认走。"""
    if not slug or not (paths.PROJECTS / slug / "project.json").is_file():
        return True
    _, config = project_context(slug)
    return quote_optional(config)


def generation_spec(request):
    """显示用户需要确认的输入身份；金额由调用方按需另行展示。"""
    refs = ", ".join(str(path) for path in getattr(request, "refs", [])) or "无"
    seed = request.seed if request.seed is not None else "随机（dry-run 种子不锁定）"
    return (f"prompt={request.prompt_path or '命令行文本'} | workflow={request.workflow} | "
            f"duration={request.duration}s | aspect={request.aspect} | "
            f"megapixels={request.megapixels} | steps={request.steps} | "
            f"seed={seed} | refs={refs}")


def client_from_args(args):
    return ComfyClient(getattr(args, "base", None), getattr(args, "poll", 5.0),
                       getattr(args, "client_id", "auto"))
