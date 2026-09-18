"""测试夹具：项目级测试都在临时目录里造项目，不依赖真实作品的版本号。"""
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from t2v import paths                      # noqa: E402
from t2v.project import init_project       # noqa: E402

VALID_PROMPT = """---
version: v001
duration: 3.0
status: draft
---
subject_definitions:
<Subject 1> is a test swordswoman in a black robe.

summary:
[reference generation] A wide shot of <Subject 1> standing on still water.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - her robe and hair stay consistent.

detailed_description:
[Shot 1] At 00:00.000 the camera holds a wide low-angle view of the lake while <Subject 1> stands still.
She lifts her left hand slowly and the water rings spread outward around her boots.

overall_soundscape:
Faint water ripples and a distant wind.

non_diegetic_music:
A single low string note.
"""


@pytest.fixture
def projects_root(tmp_path, monkeypatch):
    """把 paths.PROJECTS 指到临时目录，并放一份项目模板。"""
    root = tmp_path / "projects"
    root.mkdir()
    shutil.copytree(paths.PROJECTS / "_template", root / "_template")
    monkeypatch.setattr(paths, "PROJECTS", root)
    return root


@pytest.fixture
def demo_project(projects_root):
    project = init_project("demo-project", "Demo Project")
    write_prompt(project, "c001", "v001")
    return project


def write_prompt(project, shot, version, body=VALID_PROMPT):
    target = project / "prompts" / "shots" / shot / f"{version}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def patch_config(project, **changes):
    config = json.loads((project / "project.json").read_text(encoding="utf-8"))
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    (project / "project.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return config
