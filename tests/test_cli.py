"""CLI 行为：费用闸门、退出码，以及对真实仓库项目的冒烟校验。"""
import json

import pytest

from conftest import VALID_PROMPT, patch_config, write_prompt
from t2v import cli
from t2v.engines import h3
from t2v.engines.h3 import runner as h3_runner
from t2v.paths import ROOT

R2V = str(ROOT / "workflows/h3/r2v.api.json")
T2V = str(ROOT / "workflows/h3/t2v.api.json")


@pytest.fixture
def no_submit(monkeypatch):
    """任何真实提交都让测试失败：这些用例只能走到闸门为止。"""
    calls = []

    def fail(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("测试里不允许真的提交生成任务")

    monkeypatch.setattr(h3_runner, "execute", fail)
    return calls


def test_h3_engine_refuses_to_submit_without_both_confirmations(capsys):
    """缺确认标记就必须拒绝。只验行为，不验措辞。"""
    assert cli.main(["h3", "--workflow", T2V]) == 2
    assert capsys.readouterr().err.startswith("[error]")
    assert cli.main(["h3", "--workflow", T2V, "--execute"]) == 2
    assert capsys.readouterr().err.startswith("[error]")


def test_project_run_refuses_without_both_confirmations(demo_project, no_submit, capsys):
    """缺确认标记就必须拒绝。只验行为，不验措辞——文案会变，闸门不该因此红。"""
    assert cli.main(["run", "demo-project", "c001"]) == 2
    assert capsys.readouterr().err.startswith("[error]")
    assert cli.main(["run", "demo-project", "c001", "--execute"]) == 2
    assert capsys.readouterr().err.startswith("[error]")
    assert no_submit == []


def test_run_stops_on_a_prompt_marked_do_not_generate(demo_project, no_submit, capsys):
    write_prompt(demo_project, "c001", "v002",
                 VALID_PROMPT.replace("status: draft", "status: draft\ndo_not_generate: true\nreview_note: 已退役"))
    assert cli.main(["run", "demo-project", "c001", "--execute", "--generation-confirmed"]) == 2
    error = capsys.readouterr().err
    assert "do_not_generate" in error and "已退役" in error
    assert no_submit == []


def test_run_stops_when_inputs_fail_validation(demo_project, no_submit, capsys):
    write_prompt(demo_project, "c001", "v003", VALID_PROMPT.replace("non_diegetic_music:", "music:"))
    assert cli.main(["run", "demo-project", "c001", "--execute", "--generation-confirmed"]) == 2
    assert "输入校验失败" in capsys.readouterr().err
    assert no_submit == []


def test_plan_is_free_and_ends_with_the_confirmation_reminder(demo_project, no_submit, capsys):
    assert cli.main(["plan", "demo-project", "c001", "--seed", "20260920"]) == 0
    out = capsys.readouterr().out
    assert "[plan] c001:" in out and "seed=20260920" in out
    assert "帧数 73" in out
    # 报价默认不算（费时间），要看用 plan --quote；提交前必须确认的是 prompt 与工作流
    assert "[dry-run] 未提交" in out and "[quote]" not in out
    assert cli.GENERATION_HINT in out
    assert (demo_project / "workflows" / "c001__v001.ui.json").is_file()


def test_project_can_confirm_generation_spec_with_optional_quote(demo_project, monkeypatch, capsys):
    patch_config(demo_project, generation_confirmation={"quote": "optional"})
    assert cli.main(["plan", "demo-project", "c001", "--seed", "101"]) == 0
    out = capsys.readouterr().out
    assert "[generation]" in out and "v001.md" in out and "r2v.api.json" in out
    assert "seed=101" in out and "[quote]" not in out
    assert cli.GENERATION_HINT in out

    assert cli.main(["plan", "demo-project", "c001", "--quote"]) == 0
    assert "[quote]" in capsys.readouterr().out

    assert cli.main(["run", "demo-project", "c001", "--execute", "--cost-confirmed"]) == 2
    assert "--generation-confirmed" in capsys.readouterr().err

    calls = []
    monkeypatch.setattr(h3, "execute", lambda request, **kw: calls.append((request, kw)))
    assert cli.main(["run", "demo-project", "c001", "--execute", "--generation-confirmed"]) == 0
    assert len(calls) == 1 and calls[0][1]["cost_confirmed"] is True
    assert "[quote]" not in capsys.readouterr().out


def test_direct_h3_uses_project_generation_confirmation(demo_project, monkeypatch, capsys):
    patch_config(demo_project, generation_confirmation={"quote": "optional"})
    prompt = demo_project / "prompts/shots/c001/v001.md"
    args = ["h3", "--project", "demo-project", "--workflow", T2V,
            "--prompt-file", str(prompt), "--duration", "3", "--seed", "101"]
    assert cli.main([*args, "--dry-run"]) == 0
    assert "[generation]" in capsys.readouterr().out
    assert cli.main([*args, "--execute", "--cost-confirmed"]) == 2
    assert "--generation-confirmed" in capsys.readouterr().err

    calls = []
    monkeypatch.setattr(h3_runner, "execute", lambda request, **kw: calls.append((request, kw)))
    assert cli.main([*args, "--execute", "--generation-confirmed"]) == 0
    assert len(calls) == 1 and calls[0][1]["cost_confirmed"] is True


def test_validate_reports_failures_with_exit_code_two(demo_project, capsys):
    write_prompt(demo_project, "c001", "v002", VALID_PROMPT.replace("status: draft", "status: 待定"))
    assert cli.main(["validate", "demo-project"]) == 2
    assert "验证失败" in capsys.readouterr().err


def test_unknown_project_is_a_clean_error(capsys):
    assert cli.main(["validate", "no-such-project"]) == 2
    assert "缺少文件" in capsys.readouterr().err


def test_real_repository_shots_still_validate(capsys):
    """仓库里每个真实项目的镜头都要过校验——防的是配置漂移，不是某一个作品。

    公开仓只带 `sample-lake` 示例；私有工作台里同一条会遍历到全部在制作品。
    """
    from t2v import paths
    projects = sorted(path.name for path in paths.PROJECTS.iterdir()
                      if path.is_dir() and not path.name.startswith("_")
                      and (path / "project.json").is_file())
    assert projects, "projects/ 下至少要有一个 v2 项目"
    for slug in projects:
        assert cli.main(["validate", slug]) == 0, f"{slug} 校验未通过"
    assert "[validate] 通过" in capsys.readouterr().out


def test_graph_h3_reproduces_the_checked_in_workflow(tmp_path, capsys):
    out = tmp_path / "rebuilt.api.json"
    assert cli.main(["graph", "h3", "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(open(R2V, encoding="utf-8").read())


def test_graph_scail2_enforces_frame_and_size_rules(tmp_path, capsys):
    out = str(tmp_path / "scail2.api.json")
    assert cli.main(["graph", "scail2", "--driving", "d.mp4", "--ref", "r.png",
                     "--length", "70", "--out", out]) == 2
    assert "4n+1" in capsys.readouterr().err
    assert cli.main(["graph", "scail2", "--driving", "d.mp4", "--ref", "r.png",
                     "--mode", "maskcheck", "--out", out]) == 0


def test_every_project_points_at_a_workflow_that_exists():
    """funcontrol 那次事故就是配置指向了仓库里不存在的工作流：把这条钉成回归测试。"""
    import json
    from t2v import paths
    missing = []
    for config_path in sorted(paths.PROJECTS.glob("*/project.json")):
        engine = json.loads(config_path.read_text(encoding="utf-8")).get("engine", {})
        for key, value in engine.items():
            for workflow in ([value] if isinstance(value, str) else
                             list(value.values()) if isinstance(value, dict) else []):
                if str(workflow).endswith(".json") and not (paths.ROOT / workflow).is_file():
                    missing.append(f"{config_path.parent.name}.engine.{key} -> {workflow}")
    assert missing == [], "配置指向了不存在的工作流：" + "; ".join(missing)


def test_workflow_api_and_canvas_files_come_in_pairs():
    """synced_ui_workflow 按同名 .ui.json 找画布，缺一个就只能导出模板占位值。"""
    from t2v import paths
    for api in sorted((paths.WORKFLOWS / "h3").glob("*.api.json")):
        assert api.with_name(api.name.replace(".api.json", ".ui.json")).is_file(), f"{api} 缺同名画布版"


def test_template_files_sit_one_level_under_their_engine():
    """templates/<引擎>/<任务>.json：根下不放散件，引擎目录内平铺（规则见 workflows/README.md）。"""
    from t2v import paths
    templates = paths.WORKFLOWS / "templates"
    loose = [p.name for p in templates.glob("*.json")]
    assert loose == [], f"templates/ 根下不应有散件：{loose}"
    engines = sorted(p.name for p in templates.iterdir() if p.is_dir())
    assert engines, "templates/ 下应按引擎分目录"
    for engine in engines:
        assert list((templates / engine).glob("*.json")), f"templates/{engine}/ 是空的"
