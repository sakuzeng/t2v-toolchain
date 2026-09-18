"""SCAIL-2 角色替换引擎。

只实现通用契约（NAME / add_arguments / add_graph_arguments）。**不支持项目-镜头工作流**：
它以「实验」为单位（驱动视频 + 参考图 + --exp），没有 prompts/shots/<镜头>/vNNN.md 那一层。
因此不提供 from_project / plan / execute 等项目侧函数，`t2v plan <项目>` 会给出明确提示。
是否接入项目配置由使用方决定：引擎本身不感知项目层。
"""
from . import cli, graph, request, runner

NAME = "scail2"

add_arguments = cli.add_arguments
add_graph_arguments = cli.add_graph_arguments

__all__ = ["NAME", "add_arguments", "add_graph_arguments", "graph", "request", "runner"]
