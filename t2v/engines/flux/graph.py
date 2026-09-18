"""FLUX.2 [klein] 的 API 图构造（纯函数，不联网、不落盘）。

接线依据 ComfyUI 官方模板（2026-09-18 从 Comfy-Org/workflow_templates 取回并逐节点核对）：

    image_flux2_klein_text_to_image.json        —— 文生图，4 步蒸馏 / cfg 1
    image_flux2_klein_image_edit_9b_distilled.json —— 图像编辑 + 多参考图

两者的公共骨架：

    UNETLoader ─┐
    CLIPLoader ─┴→ CLIPTextEncode(+/-) → CFGGuider(cfg) ─┐
    Flux2Scheduler(steps,w,h) ─┐                          ├→ SamplerCustomAdvanced → VAEDecode → SaveImage
    EmptyFlux2LatentImage(w,h) ─┼→ SamplerCustomAdvanced ─┘
    RandomNoise(seed) ─────────┘

多参考图（编辑模板的做法）：每张参考图
    LoadImage → ImageScaleToTotalPixels(lanczos, 1MP) → VAEEncode → ReferenceLatent
`ReferenceLatent` 首尾相接串成一串，最后一环挂到 CFGGuider 的 **positive** 上——
这就是「角色四视图 + 场景底板 → 首帧图」能保住身份一致性的机制。

注意：蒸馏版（4 步）用 `cfg = 1`；base 版（未蒸馏）用 20–50 步、`cfg = 5`。
"""
import math
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

DISTILLED_STEPS = 4
DISTILLED_CFG = 1.0
SEED_MAX = 2 ** 31
ASPECT_RE = re.compile(r"^\s*(\d+)\s*[:：]\s*(\d+)")


def parse_aspect(aspect: str) -> Tuple[int, int]:
    match = ASPECT_RE.match(str(aspect))
    if not match:
        raise ValueError(f"比例要写成 W:H（例如 9:16），拿到的是 {aspect!r}")
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0:
        raise ValueError(f"比例必须为正：{aspect!r}")
    return width, height


def latent_size(aspect: str, megapixels: float, multiple: int = 32) -> Tuple[int, int]:
    """按比例与目标像素数算 latent 尺寸，向上取到 `multiple` 的整数倍。

    向上取整（而不是四舍五入）是为了**不低于**请求的像素预算：
    1:1 @1MP 得到 1024×1024、9:16 @1MP 得到 768×1344。multiple 默认 32——
    FLUX.2 的 VAE 是 16 倍下采样，32 的倍数在任何分辨率桶里都安全。
    """
    ratio_w, ratio_h = parse_aspect(aspect)
    scale = (float(megapixels) * 1_000_000 / (ratio_w * ratio_h)) ** 0.5
    width = max(multiple, math.ceil(ratio_w * scale / multiple) * multiple)
    height = max(multiple, math.ceil(ratio_h * scale / multiple) * multiple)
    return width, height


def resolve_seed(spec) -> int:
    seed = getattr(spec, "seed", None)
    return int(seed) if seed is not None else random.randint(0, SEED_MAX)


def build(spec, seed: int) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """→ (API 图, 本次参数)。上传后的远端文件名由 runner 回填到 LoadImage 节点。"""
    width, height = latent_size(spec.aspect, spec.megapixels)
    graph: Dict[str, Any] = {
        "1": {"class_type": "UNETLoader", "_meta": {"title": "主干"},
              "inputs": {"unet_name": spec.unet, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "_meta": {"title": "文本编码器"},
              "inputs": {"clip_name": spec.clip, "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "_meta": {"title": "VAE"},
              "inputs": {"vae_name": spec.vae}},
        "4": {"class_type": "CLIPTextEncode", "_meta": {"title": "正向提示词"},
              "inputs": {"clip": ["2", 0], "text": spec.prompt_text}},
        "5": {"class_type": "CLIPTextEncode", "_meta": {"title": "负向提示词"},
              "inputs": {"clip": ["2", 0], "text": spec.negative}},
        "6": {"class_type": "CFGGuider", "_meta": {"title": "引导"},
              "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0],
                         "cfg": float(spec.cfg)}},
        "7": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "8": {"class_type": "Flux2Scheduler",
              "inputs": {"steps": int(spec.steps), "width": width, "height": height}},
        "9": {"class_type": "EmptyFlux2LatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": int(seed)}},
        "11": {"class_type": "SamplerCustomAdvanced",
               "inputs": {"noise": ["10", 0], "guider": ["6", 0], "sampler": ["7", 0],
                          "sigmas": ["8", 0], "latent_image": ["9", 0]}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage",
               "inputs": {"images": ["12", 0], "filename_prefix": spec.prefix}},
    }

    # 参考图：串成 ReferenceLatent 链，最后一环挂到正向条件上
    conditioning: List[Any] = ["4", 0]
    for index, path in enumerate(spec.references):
        load, scale, encode, ref = (f"ref{index}_load", f"ref{index}_scale",
                                    f"ref{index}_encode", f"ref{index}_ref")
        graph[load] = {"class_type": "LoadImage", "_meta": {"title": f"<参考图 {index + 1}>"},
                       "inputs": {"image": Path(path).name}}
        graph[scale] = {"class_type": "ImageScaleToTotalPixels",
                        "inputs": {"image": [load, 0], "upscale_method": "lanczos",
                                   "megapixels": 1.0}}
        graph[encode] = {"class_type": "VAEEncode",
                         "inputs": {"pixels": [scale, 0], "vae": ["3", 0]}}
        graph[ref] = {"class_type": "ReferenceLatent",
                      "inputs": {"conditioning": conditioning, "latent": [encode, 0]}}
        conditioning = [ref, 0]
    graph["6"]["inputs"]["positive"] = conditioning

    params = {
        "kind": "flux2-klein", "unet": spec.unet, "clip": spec.clip, "vae": spec.vae,
        "width": width, "height": height, "aspect": spec.aspect,
        "megapixels": spec.megapixels, "steps": int(spec.steps), "cfg": float(spec.cfg),
        "seed": int(seed), "negative": spec.negative,
        "references": [str(path) for path in spec.references],
        "prompt": spec.prompt_text[:200],
    }
    return graph, params


def uploads(spec) -> List[Tuple[Path, str, str, str]]:
    """需要先 POST /upload/image 的本机文件 → (路径, 节点 id, 字段, 标签)。"""
    return [(Path(path), f"ref{index}_load", "image", f"<参考图 {index + 1}>")
            for index, path in enumerate(spec.references)]
