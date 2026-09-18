"""项目配置、路径解析、资产别名与新项目初始化。"""
import json
import os
from pathlib import Path
import re
import shutil

from . import paths
from .errors import ProjectError

# 这些一级目录一定在项目内部；其余相对路径先按项目内找，找不到再按仓库根找。
PROJECT_LOCAL_ROOTS = {"assets", "creative", "deliverables", "docs", "experiments", "prompts", "references", "runs"}
SCHEMA_VERSION = 2
# 不跟着模板进新项目的东西：系统垃圾，以及只有 v1 迁移才会用到的目录
# （`ref/` 是 v1 的参考目录名，`archive/layout-v1/` 由 migrate-v1 创建）。
TEMPLATE_SKIP = (".DS_Store", "ref", "archive")


def projects_root():
    """每次调用时读，测试换 paths.PROJECTS 即可指向临时目录。"""
    return paths.PROJECTS


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ProjectError(f"缺少文件：{path}")
    except json.JSONDecodeError as exc:
        raise ProjectError(f"JSON 无效：{path}:{exc.lineno}:{exc.colno} {exc.msg}")


def project_context(slug):
    project = projects_root() / slug
    config_path = project / "project.json"
    config = load_json(config_path)
    if config.get("schema_version") != SCHEMA_VERSION:
        raise ProjectError(f"{config_path} 的 schema_version 必须为 {SCHEMA_VERSION}")
    if config.get("slug") != slug:
        raise ProjectError(f"project.json slug={config.get('slug')!r} 与目录 {slug!r} 不一致")
    return project, config


def project_path(project, config, key, default):
    return project / config.get("paths", {}).get(key, default)


def shot_ids(project, config):
    base = project_path(project, config, "prompts", "prompts/shots")
    return sorted(path.name for path in base.iterdir() if path.is_dir()) if base.is_dir() else []


def find_prompt(project, config, shot, version=None):
    shot_dir = project_path(project, config, "prompts", "prompts/shots") / shot
    if shot_dir.is_dir():
        if version:
            name = version if version.endswith(".md") else version + ".md"
            candidates = [shot_dir / name]
        else:
            candidates = sorted(shot_dir.glob("v[0-9][0-9][0-9].md"), reverse=True)
        if candidates and candidates[0].is_file():
            return candidates[0]
    exact = project / "prompts" / f"{shot}.md"
    if exact.is_file():
        return exact
    legacy = sorted((project / "prompts").glob(f"{shot}_*.md"))
    if legacy:
        return legacy[0]
    raise ProjectError(f"找不到镜头 {shot} 的 prompt（期望 {shot_dir}/vNNN.md）")


def resolve_project_path(project, value):
    path = Path(value)
    if path.is_absolute():
        return path
    inside = project / path
    if path.parts and path.parts[0] in PROJECT_LOCAL_ROOTS:
        return inside
    return inside if inside.exists() else paths.ROOT / path


def resolve_asset(project, config, value):
    if not isinstance(value, str):
        raise ProjectError(f"资产引用必须是字符串：{value!r}")
    if value.startswith("@"):
        alias = value[1:]
        entry = config.get("assets", {}).get(alias)
        if entry is None:
            raise ProjectError(f"未知资产别名：{value}")
        value = entry.get("path") if isinstance(entry, dict) else entry
    return resolve_project_path(project, value)


def init_project(slug, title=None):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise ProjectError("项目代号只能使用小写字母、数字和连字符")
    target = projects_root() / slug
    if target.exists():
        raise ProjectError(f"项目已存在：{target}")
    shutil.copytree(projects_root() / "_template", target, ignore=shutil.ignore_patterns(*TEMPLATE_SKIP))
    for path in target.rglob("*"):
        if path.is_file() and path.suffix in (".md", ".json", ".sh"):
            text = path.read_text(encoding="utf-8")
            text = text.replace("__PROJECT_SLUG__", slug).replace("__PROJECT_TITLE__", title or slug)
            path.write_text(text, encoding="utf-8")
    os.chmod(target / "run.sh", 0o755)
    return target
