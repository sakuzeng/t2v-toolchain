"""FLUX.2 [klein] 生图引擎。

契约（见 t2v/engines/__init__.py）：只实现通用契约——NAME / add_arguments / add_graph_arguments。
**不实现项目-镜头契约**：那套梯度是给 H3 的 `prompts/shots/<镜头>/vNNN.md` 用的，
出图走 `t2v flux <项目> <生图 prompt 文件>`（`prompts/scene/…` 与 `prompts/shots/<镜头>/keyframe.md`）。
"""
from . import cli, graph, prompt, runner

NAME = "flux"

add_arguments = cli.add_arguments
add_graph_arguments = cli.add_graph_arguments

__all__ = ["NAME", "add_arguments", "add_graph_arguments", "cli", "graph", "prompt", "runner"]
