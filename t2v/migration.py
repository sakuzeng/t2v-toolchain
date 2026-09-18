"""把 v1 项目按 v2 布局复制一份，不移动也不删除旧文件。"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import shutil

from .errors import ProjectError
from .paths import ROOT
RUN_RE = re.compile(r"^(?P<name>.+)__(?P<ts>\d{8}-\d{6})__(?P<pid>[0-9a-f]{8})(?P<ui>\.ui)?(?P<ext>\.[^.]+)$")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source, dest, execute, force, records, category):
    item = {
        "category": category,
        "source": str(source.relative_to(ROOT)),
        "destination": str(dest.relative_to(ROOT)),
        "bytes": source.stat().st_size,
        "sha256": sha256(source),
    }
    if dest.exists() and not force:
        item["action"] = "kept-existing"
    elif execute:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(source), str(dest))
        item["action"] = "copied"
    else:
        item["action"] = "would-copy"
    records.append(item)


def infer_shot(name):
    match = re.match(r"c(\d+)([a-z]?)", name, re.I)
    if match:
        return f"c{int(match.group(1)):03d}{match.group(2).lower()}-legacy"
    match = re.match(r"s(\d+)", name, re.I)
    if match:
        return f"s{int(match.group(1)):03d}-legacy"
    if name.startswith("asset_"):
        return "asset-legacy"
    return "unclassified-legacy"


def run_destination(source, project, match):
    name, stamp, pid = match.group("name"), match.group("ts"), match.group("pid")
    run_id = f"{stamp}_legacy_{pid}"
    run = project / "runs" / infer_shot(name) / run_id
    if match.group("ui"):
        filename = "workflow.ui.json"
    elif match.group("ext") == ".mp4":
        filename = "output.mp4"
    elif match.group("ext") == ".json":
        filename = "run.json"
    else:
        filename = "output" + match.group("ext")
    return run, run / filename, run_id, name, stamp, pid


def migrate_references(project, execute, force, records):
    legacy = project / "ref"
    if not legacy.is_dir():
        return
    for source in sorted(path for path in legacy.rglob("*") if path.is_file() and path.name != ".gitkeep"):
        relative = source.relative_to(legacy)
        if relative.parts[0] == "clips":
            dest = project / "references" / "clips" / Path(*relative.parts[1:])
        elif relative.parts[0] == "control":
            dest = project / "references" / "controls" / "legacy" / Path(*relative.parts[1:])
        elif relative.parts[0] == "shots":
            dest = project / "references" / "analysis" / "shots" / Path(*relative.parts[1:])
        elif len(relative.parts) == 1 and source.suffix.lower() in (".mp4", ".mov", ".mkv"):
            dest = project / "references" / "source" / source.name
        else:
            dest = project / "references" / "analysis" / relative
        copy_file(source, dest, execute, force, records, "reference")


def migrate_assets(project, execute, force, records):
    assets = project / "assets"
    canonical_sources = {
        "chiling_face_ref.png", "chiling_v8_front_view.png",
        "chiling_skirt_ref.png", "sword_chiling_feather_v1.png",
    }
    for source in sorted(path for path in assets.iterdir() if path.is_file() and path.name != ".gitkeep"):
        if source.name in canonical_sources:
            continue
        dest = assets / "candidates" / "legacy" / source.name
        copy_file(source, dest, execute, force, records, "asset-candidate")
    legacy_archive = assets / "archive"
    if legacy_archive.is_dir():
        for source in sorted(path for path in legacy_archive.rglob("*") if path.is_file() and path.name != ".gitkeep"):
            if "legacy" in source.relative_to(legacy_archive).parts:
                continue
            dest = assets / "archive" / "legacy" / source.relative_to(legacy_archive)
            copy_file(source, dest, execute, force, records, "asset-archive")


def migrate_outputs(project, execute, force, records):
    outputs = project / "outputs"
    index_items = []
    groups = {}
    loose = []
    if not outputs.is_dir():
        return index_items, groups, loose
    for source in sorted(path for path in outputs.iterdir() if path.is_file()):
        match = RUN_RE.match(source.name)
        if not match:
            loose.append(source)
            dest = project / "experiments" / "legacy-import" / "artifacts" / source.name
            copy_file(source, dest, execute, force, records, "legacy-artifact")
            continue
        run, dest, run_id, name, stamp, pid = run_destination(source, project, match)
        copy_file(source, dest, execute, force, records, "legacy-run")
        group = groups.setdefault(run_id, {
            "schema_version": 2, "run_id": run_id, "project": project.name,
            "shot": infer_shot(name), "legacy_name": name, "prompt_id": pid,
            "submitted_at": stamp, "path": str(run.relative_to(project / "runs")), "files": []
        })
        group["files"].append(source.name)
    for group in sorted(groups.values(), key=lambda item: item["run_id"]):
        index_items.append({key: group[key] for key in ("run_id", "project", "shot", "prompt_id", "submitted_at", "path")})
        if execute:
            run = project / "runs" / group["path"]
            run.mkdir(parents=True, exist_ok=True)
            (run / "import.json").write_text(json.dumps(group, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return index_items, groups, loose


def merge_index(project, items, execute):
    index_path = project / "runs" / "index.jsonl"
    existing = []
    if index_path.exists():
        existing = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    known = {item.get("run_id") for item in existing}
    additions = [item for item in items if item["run_id"] not in known]
    if execute and additions:
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with index_path.open("a", encoding="utf-8") as stream:
            for item in additions:
                stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    return len(additions)


def migrate(slug, execute=False, force=False):
    project = ROOT / "projects" / slug
    if not (project / "project.json").is_file():
        raise ProjectError(f"缺少 v2 project.json：{project}")
    records = []
    migrate_assets(project, execute, force, records)
    migrate_references(project, execute, force, records)
    index_items, groups, loose = migrate_outputs(project, execute, force, records)
    additions = merge_index(project, index_items, execute)
    manifest = {
        "schema_version": 1,
        "mode": "copy-only",
        "executed": execute,
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "project": slug,
        "summary": {
            "source_files": len(records), "run_groups": len(groups),
            "loose_output_artifacts": len(loose), "new_index_rows": additions,
            "bytes": sum(item["bytes"] for item in records),
        },
        "records": records,
    }
    manifest_path = project / "docs" / "migration" / "layout-v1-import.json"
    if execute:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        legacy_note = project / "experiments" / "legacy-import" / "README.md"
        legacy_note.parent.mkdir(parents=True, exist_ok=True)
        legacy_note.write_text(
            "# v1 未归组产物\n\n这里存放无法由 `<name>__<timestamp>__<prompt-id>` 关联到单次生成的旧拼图和日志。"
            "媒体在 `artifacts/` 且被 Git 忽略；文件级来源与 SHA-256 见 `../../docs/migration/layout-v1-import.json`。\n",
            encoding="utf-8",
        )
    prefix = "migrate" if execute else "dry-run"
    print(f"[{prefix}] {len(records)} 个文件，{len(groups)} 个 run，{len(loose)} 个散件，{sum(item['bytes'] for item in records)/1024/1024:.1f} MiB")
    print(f"[{prefix}] 索引新增 {additions} 行；旧目录不会移动或删除")
    if not execute:
        print(f"[next] python3 -m t2v migrate-v1 {slug} --execute")
    else:
        print(f"[manifest] {manifest_path}")
    return manifest
