"""一次 H3 生成请求的完整描述，以及它的免费报价。

两个构造入口——项目命令走 from_project()，`t2v h3` 直接由命令行参数构造——
共用同一个 dataclass，参数的类型与默认值只定义一次。
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...errors import ProjectError
from ...frontmatter import read as read_frontmatter
from ...project import find_prompt, project_context, project_path, resolve_asset, resolve_project_path
from .prompt import expected_frames

DEFAULTS = {"megapixels": 0.4, "aspect": "16:9 (Widescreen)", "steps": 20, "retime_fps": 24.0}


@dataclass
class H3Request:
    """送给 H3 引擎的全部内容：输入、采样参数、后期处理与产物落点。"""
    workflow: Path
    prompt_text: str = ""
    prompt_path: Optional[Path] = None
    # 身份
    mode: str = "r2v"              # base（T2V/I2V 三段式）或 r2v（六段式），决定 prompt 校验哪些字段
    project: Optional[str] = None
    shot: Optional[str] = None
    name: str = "run"
    # 采样参数（None = 沿用工作流模板里的值）
    megapixels: Optional[float] = None
    aspect: Optional[str] = None
    duration: Optional[float] = None
    steps: Optional[int] = None
    seed: Optional[int] = None
    turbo: bool = False
    # 参考输入
    refs: List[Path] = field(default_factory=list)
    ref_image_size: Optional[str] = None
    ref_video: Optional[Path] = None
    ref_video_audio: bool = False
    first_frame: Optional[Path] = None
    # 后期
    strip_audio: bool = False
    retime_output_frames: Optional[int] = None
    retime_fps: float = DEFAULTS["retime_fps"]
    # 产物落点
    out_dir: Optional[Path] = None
    capsule_root: Optional[Path] = None
    export_ui: Optional[Path] = None
    workflow_label: Optional[str] = None
    # 上下文
    gpu_hourly: float = 0.0
    config: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def capsule(self):
        return bool(self.capsule_root and self.shot)

    @property
    def frames(self):
        return expected_frames(self.duration) if self.duration is not None else None

    def input_paths(self):
        """本机必须存在的输入文件。"""
        found = [self.workflow, *self.refs]
        found += [path for path in (self.first_frame, self.ref_video) if path]
        return found


def _pick(override, meta, defaults, key, fallback=None):
    if override is not None:
        return override
    if key in meta:
        return meta[key]
    return defaults.get(key, fallback)


def from_project(slug, shot, overrides=None):
    """项目 + 镜头 → H3Request。overrides 是命令行给的临时覆盖（argparse Namespace 或 dict）。"""
    overrides = _as_dict(overrides)
    project, config = project_context(slug)
    prompt_path = find_prompt(project, config, shot, overrides.get("version"))
    meta, body = read_frontmatter(prompt_path)
    defaults = config.get("defaults", {})

    workflow = meta.get("workflow", config.get("engine", {}).get("workflow"))
    if not workflow:
        raise ProjectError(f"{slug} 的 project.json 没有配置 engine.workflow")
    duration = _pick(overrides.get("duration"), meta, defaults, "duration")
    if duration is None:
        raise ProjectError(f"{prompt_path} 缺少 duration")
    refs = meta.get("refs", defaults.get("refs", []))
    if isinstance(refs, str):
        refs = [refs]
    first_frame = _pick(overrides.get("first_frame"), meta, defaults, "first_frame")
    version = meta.get("version", prompt_path.stem)
    return H3Request(
        workflow=resolve_project_path(project, workflow),
        prompt_text=body,
        prompt_path=prompt_path,
        mode=config.get("engine", {}).get("mode", "r2v"),
        project=slug,
        shot=shot,
        name=shot,
        megapixels=float(_pick(overrides.get("megapixels"), meta, defaults, "megapixels", DEFAULTS["megapixels"])),
        aspect=_pick(overrides.get("aspect"), meta, defaults, "aspect", DEFAULTS["aspect"]),
        duration=float(duration),
        steps=int(_pick(overrides.get("steps"), meta, defaults, "steps", DEFAULTS["steps"])),
        seed=overrides.get("seed"),
        turbo=bool(defaults.get("turbo", False)),
        refs=[resolve_asset(project, config, ref) for ref in refs],
        ref_image_size=meta.get("ref_image_size", defaults.get("ref_image_size")),
        first_frame=resolve_asset(project, config, first_frame) if first_frame else None,
        strip_audio=bool(meta.get("strip_audio", defaults.get("strip_audio", False))),
        retime_output_frames=meta.get("retime_output_frames"),
        retime_fps=meta.get("retime_fps", DEFAULTS["retime_fps"]),
        capsule_root=project_path(project, config, "runs", "runs"),
        export_ui=project / "workflows" / f"{shot}__{version}.ui.json",
        workflow_label=f"{shot} · {version}",
        gpu_hourly=float(config.get("cost", {}).get("gpu_hourly", 0.0)),
        config=config,
        meta=meta,
    )


def _as_dict(overrides):
    if overrides is None:
        return {}
    if isinstance(overrides, dict):
        return {key: value for key, value in overrides.items() if value is not None}
    return {key: value for key, value in vars(overrides).items() if value is not None}


def quote(request):
    """按项目配置的 GPU 单价与速度基线估价。没配基线就明说，不编数字。"""
    cost = request.config.get("cost", {})
    rates = cost.get("estimated_render_minutes_per_second", {})
    rate = rates.get(str(request.megapixels), rates.get(f"{request.megapixels:g}"))
    hourly = float(cost.get("gpu_hourly", 0.0))
    if not rate or not hourly:
        return "费用估算：项目尚未配置可用的 GPU 单价/速度基线。"
    render_minutes = float(rate) * request.duration
    session_minutes = render_minutes + float(cost.get("startup_minutes", 0))
    low, high = render_minutes * hourly / 60 * 0.8, render_minutes * hourly / 60 * 1.25
    session_low, session_high = session_minutes * hourly / 60 * 0.8, session_minutes * hourly / 60 * 1.25
    currency = cost.get("currency", "CNY")
    symbol = "¥" if currency == "CNY" else currency + " "
    return (f"dry-run 报价：渲染约 {render_minutes:.1f} 分钟，生成 {symbol}{low:.2f}–{high:.2f}；"
            f"含启动约 {session_minutes:.1f} 分钟，整次会话 {symbol}{session_low:.2f}–{session_high:.2f}。")
