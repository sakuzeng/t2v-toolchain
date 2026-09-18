"""MiniMax H3 引擎。

契约（见 t2v/engines/__init__.py）：
- NAME / add_arguments / add_graph_arguments  —— 所有引擎都要有
- from_project / validate / plan / execute / quote —— 支持项目-镜头工作流的引擎才有
"""
from . import cli, graph, official, prompt, request, runner

NAME = "h3"

add_arguments = cli.add_arguments
add_graph_arguments = cli.add_graph_arguments

from_project = request.from_project
quote = request.quote
validate = prompt.validate_prompt
plan = runner.plan
execute = runner.execute

__all__ = ["NAME", "add_arguments", "add_graph_arguments", "from_project", "quote",
           "validate", "plan", "execute", "graph", "official", "prompt", "request", "runner"]
