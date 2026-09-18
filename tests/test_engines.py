"""引擎契约：加一个引擎时，这些测试就是它必须满足的清单。"""
import json

import pytest

from conftest import patch_config
from t2v import cli, engines
from t2v.errors import ProjectError

UNIVERSAL = ("NAME", "add_arguments", "add_graph_arguments")


def test_registry_keys_match_each_engine_name():
    assert engines.names() == ["flux", "h3", "scail2"]
    for name in engines.names():
        assert engines.get(name).NAME == name


@pytest.mark.parametrize("name", engines.names())
def test_every_engine_satisfies_the_universal_contract(name):
    engine = engines.get(name)
    for attribute in UNIVERSAL:
        assert hasattr(engine, attribute), f"{name} 缺少 {attribute}"
    assert callable(engine.add_arguments) and callable(engine.add_graph_arguments)


@pytest.mark.parametrize("name", engines.names())
def test_project_hooks_are_all_or_nothing(name):
    """半套项目契约最危险：cmd_plan 会崩在 AttributeError 而不是给出提示。"""
    engine = engines.get(name)
    present = [hook for hook in engines.PROJECT_HOOKS if hasattr(engine, hook)]
    assert present in ([], list(engines.PROJECT_HOOKS)), f"{name} 只实现了部分项目契约：{present}"


def test_h3_drives_projects_and_scail2_does_not():
    assert engines.supports_project_shots(engines.get("h3"))
    assert not engines.supports_project_shots(engines.get("scail2"))


def test_unknown_engine_names_the_available_ones():
    with pytest.raises(ProjectError, match="未知引擎"):
        engines.get("wan-animate2")
    with pytest.raises(ProjectError, match="h3, scail2"):
        engines.get("nope")


@pytest.mark.parametrize("name", engines.names())
def test_every_engine_registers_both_cli_surfaces(name):
    commands = cli.build_parser()._subparsers._group_actions[0].choices
    assert name in commands, f"{name} 没注册 t2v {name} 子命令"
    assert name in commands["graph"]._subparsers._group_actions[0].choices, f"{name} 没注册 t2v graph {name}"


def test_project_dispatches_on_the_configured_engine(demo_project):
    assert cli.project_engine("demo-project").NAME == "h3"
    patch_config(demo_project, engine={"name": "scail2"})
    with pytest.raises(ProjectError, match="不支持项目-镜头工作流"):
        cli.project_engine("demo-project")
    patch_config(demo_project, engine={"name": "nope"})
    with pytest.raises(ProjectError, match="未知引擎"):
        cli.project_engine("demo-project")


def test_projects_without_an_engine_name_default_to_h3(demo_project):
    config = json.loads((demo_project / "project.json").read_text(encoding="utf-8"))
    del config["engine"]["name"]
    (demo_project / "project.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
    assert cli.project_engine("demo-project").NAME == engines.DEFAULT == "h3"


def test_every_repository_project_names_a_registered_engine():
    from t2v import paths
    for path in sorted(paths.PROJECTS.glob("*/project.json")):
        name = json.loads(path.read_text(encoding="utf-8")).get("engine", {}).get("name", engines.DEFAULT)
        assert name in engines.REGISTRY, f"{path.parent.name} 指向未注册的引擎 {name}"
