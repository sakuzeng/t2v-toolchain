"""生图 prompt 的解析：一份 .md（frontmatter + 英文正文）→ ImageSpec。

与 H3 的 shot prompt 不同，生图 prompt 不在 `prompts/shots/<镜头>/vNNN.md` 那套版本阶梯里，
而是资产级的：`prompts/scene/<场景>/vNNN.md` 与 `prompts/shots/<镜头>/keyframe.md`。
它们的 frontmatter 自带 `references`（参考图）与 `target`（评审通过后要落的正式路径）。
字段多一个 `references`，少一个 `duration`——不需要 H3 那套时长/帧数校验。
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...errors import ProjectError
from ...frontmatter import read as read_frontmatter
from ...project import project_context, resolve_asset, resolve_project_path

DEFAULTS: Dict[str, Any] = {
    "unet": "flux-2-klein-9b.safetensors",
    "clip": "qwen_3_8b_fp8mixed.safetensors",
    "vae": "flux2-vae.safetensors",
    "steps": 4,
    "cfg": 1.0,
    "megapixels": 1.0,
    "aspect": "1:1",
}


@dataclass
class ImageSpec:
    """一次出图的全部输入；`prompt_text` 是正文（真正送进文本编码器的部分）。"""
    project: str
    prompt_path: Path
    prompt_text: str
    prompt_id: str
    image_id: str
    target: Optional[Path] = None
    references: List[Path] = field(default_factory=list)
    aspect: str = DEFAULTS["aspect"]
    megapixels: float = DEFAULTS["megapixels"]
    steps: int = DEFAULTS["steps"]
    cfg: float = DEFAULTS["cfg"]
    seed: Optional[int] = None
    negative: str = ""
    unet: str = DEFAULTS["unet"]
    clip: str = DEFAULTS["clip"]
    vae: str = DEFAULTS["vae"]
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def prefix(self) -> str:
        return f"flux2/{self.image_id}"

    def describe(self) -> str:
        refs = ", ".join(str(path) for path in self.references) or "无"
        seed = self.seed if self.seed is not None else "随机"
        return (f"image={self.image_id} | prompt={self.prompt_path} | "
                f"unet={self.unet} | aspect={self.aspect} | megapixels={self.megapixels} | "
                f"steps={self.steps} | cfg={self.cfg} | seed={seed} | refs={refs}")


def _pick(overrides, meta, key, default=None):
    if overrides.get(key) is not None:
        return overrides[key]
    if key in meta and meta[key] is not None:
        return meta[key]
    return DEFAULTS.get(key, default)


def from_file(slug: str, prompt_file: str, overrides=None) -> ImageSpec:
    overrides = dict(overrides or {})
    project, config = project_context(slug)
    path = resolve_project_path(project, prompt_file)
    if not path.is_file():
        raise ProjectError(f"找不到生图 prompt：{path}")
    meta, body = read_frontmatter(path)
    if not body.strip():
        raise ProjectError(f"{path}: 正文是空的——正文才是送进模型的提示词")

    raw_refs = meta.get("references") or []
    if isinstance(raw_refs, str):
        raw_refs = [raw_refs]
    references = [resolve_asset(project, config, value) for value in raw_refs]

    target = meta.get("target")
    prompt_id = str(meta.get("id") or f"{slug}/{path.parent.name}")
    parts = [part for part in prompt_id.split("/")[1:]] or [path.parent.name]
    return ImageSpec(
        project=slug,
        prompt_path=path,
        prompt_text=body.strip(),
        prompt_id=prompt_id,
        image_id="-".join(parts),
        target=resolve_project_path(project, target) if target else None,
        references=references,
        aspect=str(_pick(overrides, meta, "aspect")),
        megapixels=float(_pick(overrides, meta, "megapixels")),
        steps=int(_pick(overrides, meta, "steps")),
        cfg=float(_pick(overrides, meta, "cfg")),
        seed=overrides.get("seed") if overrides.get("seed") is not None else meta.get("seed"),
        negative=str(meta.get("negative") or ""),
        unet=str(_pick(overrides, meta, "unet")),
        clip=str(_pick(overrides, meta, "clip")),
        vae=str(_pick(overrides, meta, "vae")),
        meta=meta,
    )


def validate(spec: ImageSpec):
    """只做本机可查的事：模型名非空、参考图与正文存在、比例可解析。"""
    errors, warnings = [], []
    for label, value in (("unet", spec.unet), ("clip", spec.clip), ("vae", spec.vae)):
        if not value:
            errors.append(f"{spec.prompt_path}: frontmatter/默认值缺少 {label}")
    if not spec.references and spec.meta.get("kind") == "keyframe":
        warnings.append(f"{spec.prompt_path}: 这看起来是首帧图但没有 references——"
                        f"首帧图应当至少参考场景底板")
    for path in spec.references:
        if not path.is_file():
            errors.append(f"缺少输入：{path}")
    try:
        from .graph import latent_size
        latent_size(spec.aspect, spec.megapixels)
    except Exception as exc:                     # noqa: BLE001 - 比例写错就报出来
        errors.append(f"{spec.prompt_path}: aspect {spec.aspect!r} 无法解析（{exc}）")
    if spec.steps < 1:
        errors.append(f"{spec.prompt_path}: steps 必须 ≥ 1")
    return errors, warnings
