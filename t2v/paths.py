"""仓库内的固定路径。测试通过改这里的模块属性来换项目根。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"
WORKFLOWS = ROOT / "workflows"
CLIENT_CACHE = ROOT / ".comfy_client_id"
