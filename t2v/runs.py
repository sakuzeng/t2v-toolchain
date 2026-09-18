"""run capsule 的选取、六审表、交付晋级与可迁移打包。"""
import datetime as dt
import json
from pathlib import Path
import shutil
import tarfile

from .errors import ProjectError
from .project import project_path

REVIEW_TEMPLATE = (
    "# Run review\n\n"
    "- Project: `{project}`\n- Shot: `{shot}`\n- Run: `{run}`\n"
    "- Decision: pending\n\n"
    "## 六审\n\n"
    "| 维度 | 结论 | 证据/时间码 | 后续修改 |\n|---|---|---|---|\n"
    "| 叙事与动作 | pending | | |\n| 主体一致性 | pending | | |\n"
    "| 构图与运镜 | pending | | |\n| 时序与连续性 | pending | | |\n"
    "| 美术与光影 | pending | | |\n| 技术瑕疵与声音 | pending | | |\n\n"
    "## 结论\n\n- [ ] reject\n- [ ] iterate\n- [ ] candidate\n- [ ] final\n"
)
PACK_EXCLUDED = {"outputs", "ref", "archive", "cache", "__pycache__"}


def runs_root(project, config, shot=None):
    root = project_path(project, config, "runs", "runs")
    return root / shot if shot else root


def run_dirs(project, config, shot):
    root = runs_root(project, config, shot)
    return sorted((path for path in root.iterdir() if path.is_dir()), reverse=True) if root.is_dir() else []


def choose_run(project, config, shot, run_id=None):
    if run_id:
        path = runs_root(project, config, shot) / run_id
        if not path.is_dir():
            raise ProjectError(f"run 不存在：{path}")
        return path
    choices = run_dirs(project, config, shot)
    if not choices:
        raise ProjectError(f"镜头 {shot} 没有 run")
    return choices[0]


def write_review(project, config, slug, shot, run_id=None, force=False):
    run = choose_run(project, config, shot, run_id)
    qa = run / "qa"
    qa.mkdir(exist_ok=True)
    review = qa / "review.md"
    if review.exists() and not force:
        raise ProjectError(f"评审已存在：{review}（需要重建时传 --force）")
    review.write_text(REVIEW_TEMPLATE.format(project=slug, shot=shot, run=run.name), encoding="utf-8")
    return review


def promote_run(project, config, slug, shot, run_id=None, tier="preview", force=False):
    run = choose_run(project, config, shot, run_id)
    videos = sorted(run.glob("*.mp4"))
    if not videos:
        raise ProjectError(f"run 中没有 mp4：{run}")
    source = run / "picture.mp4" if (run / "picture.mp4").is_file() else videos[0]
    dest_root = project_path(project, config, "deliverables", "deliverables") / tier
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / f"{shot}__{run.name}.mp4"
    if dest.exists() and not force:
        raise ProjectError(f"交付物已存在：{dest}（需要覆盖时传 --force）")
    shutil.copy2(source, dest)
    dest.with_suffix(".json").write_text(json.dumps({
        "project": slug, "shot": shot, "run_id": run.name, "tier": tier,
        "source": str(source.relative_to(project)),
        "promoted_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dest


def pack_project(project, config, slug, out=None, include_runs=False):
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = Path(out).resolve() if out else project / "deliverables" / f"{slug}__{stamp}.tar.gz"
    dest.parent.mkdir(parents=True, exist_ok=True)
    runs_name = config.get("paths", {}).get("runs", "runs")
    with tarfile.open(str(dest), "w:gz") as archive:
        for path in sorted(project.rglob("*")):
            relative = path.relative_to(project)
            if any(part in PACK_EXCLUDED for part in relative.parts) or path == dest:
                continue
            if not include_runs and relative.parts[0] == runs_name and relative != Path(runs_name) / "index.jsonl":
                continue
            archive.add(str(path), arcname=str(Path(slug) / relative), recursive=False)
    return dest
