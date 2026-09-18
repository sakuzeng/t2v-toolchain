"""包内统一异常：库代码抛异常，只有 cli.main 负责翻成退出码。"""


class T2VError(Exception):
    """所有可预期的用户错误的基类；cli 捕获后打印 [error] 并退出码 2。"""


class ProjectError(T2VError):
    """项目配置、路径或资产解析失败。"""


class PromptError(T2VError):
    """prompt 文件本身有问题（frontmatter、必填字段）。"""


class GraphError(T2VError):
    """工作流 JSON 与请求不匹配（缺节点、节点类型不对）。"""


class ComfyError(T2VError):
    """ComfyUI 拒绝任务或执行失败。"""


class CostGuardError(T2VError):
    """未通过费用确认就试图提交付费任务。"""
