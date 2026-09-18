"""run capsule 的选取、六审表、交付晋级与打包。"""
import json
import tarfile

import pytest

from t2v import project as project_mod, runs as runs_mod
from t2v.engines.capsule import RunCapsule
from t2v.errors import ProjectError


@pytest.fixture
def project_with_run(demo_project):
    run = demo_project / "runs" / "c001" / "20260916-120000_seed1_abcdef12"
    run.mkdir(parents=True)
    (run / "output.mp4").write_bytes(b"test-video")
    _, config = project_mod.project_context("demo-project")
    return demo_project, config, run


def test_latest_run_wins_and_unknown_run_id_is_reported(project_with_run):
    project, config, run = project_with_run
    assert runs_mod.choose_run(project, config, "c001") == run
    with pytest.raises(ProjectError, match="run 不存在"):
        runs_mod.choose_run(project, config, "c001", "nope")
    with pytest.raises(ProjectError, match="没有 run"):
        runs_mod.choose_run(project, config, "c999")


def test_review_sheet_is_written_once_unless_forced(project_with_run):
    project, config, run = project_with_run
    review = runs_mod.write_review(project, config, "demo-project", "c001")
    assert review == run / "qa" / "review.md"
    assert "六审" in review.read_text(encoding="utf-8")
    with pytest.raises(ProjectError, match="评审已存在"):
        runs_mod.write_review(project, config, "demo-project", "c001")
    runs_mod.write_review(project, config, "demo-project", "c001", force=True)


def test_promotion_copies_the_picture_master_with_a_manifest(project_with_run):
    project, config, run = project_with_run
    (run / "picture.mp4").write_bytes(b"picture-master")
    dest = runs_mod.promote_run(project, config, "demo-project", "c001")
    assert dest.read_bytes() == b"picture-master"
    manifest = json.loads(dest.with_suffix(".json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == run.name and manifest["tier"] == "preview"
    with pytest.raises(ProjectError, match="交付物已存在"):
        runs_mod.promote_run(project, config, "demo-project", "c001")


def test_pack_keeps_the_index_but_drops_run_media(project_with_run, tmp_path):
    project, config, _ = project_with_run
    package = runs_mod.pack_project(project, config, "demo-project", out=str(tmp_path / "demo.tar.gz"))
    with tarfile.open(package) as archive:
        names = archive.getnames()
    assert "demo-project/runs/index.jsonl" in names
    assert "demo-project/project.json" in names
    assert not any(name.endswith("output.mp4") for name in names)


def test_capsule_index_row_records_a_relative_path(tmp_path):
    capsule = RunCapsule(tmp_path / "runs" / "c001" / "run-1",
                         index_path=tmp_path / "runs" / "index.jsonl", subdirs=("logs", "qa"))
    assert (capsule.dir / "logs").is_dir() and (capsule.dir / "qa").is_dir()
    capsule.append_index({"run_id": "run-1"})
    row = json.loads((tmp_path / "runs" / "index.jsonl").read_text(encoding="utf-8").strip())
    assert row == {"run_id": "run-1", "path": "c001/run-1"}


TEMPLATE_ENTRIES = {
    "project.json", "README.md", "PROGRESS.md", "run.sh",
    "creative", "prompts", "assets", "references", "experiments",
    "workflows", "runs", "deliverables", "docs",
}


def test_new_project_matches_the_documented_tree(projects_root):
    """t2v init 造出来的必须与 docs/guide/PROJECT_SYSTEM.md 的标准树一致，一项不多一项不少。"""
    from t2v.project import init_project
    target = init_project("fresh-project", "Fresh")
    assert {p.name for p in target.iterdir()} == TEMPLATE_ENTRIES


def test_new_project_carries_no_v1_leftovers(projects_root):
    """ref/ 是 v1 的参考目录名，archive/layout-v1/ 只有 migrate-v1 才创建；新项目都不该有。"""
    from t2v.project import init_project
    target = init_project("fresh-project", "Fresh")
    assert not (target / "ref").exists()
    assert not (target / "archive").exists()
    assert not (target / "NOTES.md").exists(), "工作笔记只在 creative/NOTES.md，根级不留存根"
    assert (target / "creative" / "NOTES.md").is_file()


def test_documented_tree_and_template_do_not_drift():
    """标准树文档与模板出厂内容必须互相认账——它们曾经差了 5 项。"""
    import re
    from t2v import paths
    spec = (paths.ROOT / "docs/guide/PROJECT_SYSTEM.md").read_text(encoding="utf-8")
    tree = spec[spec.index("```text"):spec.index("```", spec.index("```text") + 7)]
    documented = {name.rstrip("/") for name in re.findall(r"^[├└]── ([^\s#]+)", tree, re.M)}
    documented = {name.split("/")[0] for name in documented}
    assert documented == TEMPLATE_ENTRIES
