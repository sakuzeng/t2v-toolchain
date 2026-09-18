"""SCAIL-2 实验请求。与 H3 不同，它以「实验」而非「项目镜头」为单位，因此不实现 from_project。"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from ... import paths

# 5090 实测（2026-09-08）：full turbo 6 步 864×480×69 帧 107 s；maskcheck 14 s。
# 非 turbo 按步数线性外推；非 turbo 40 步 CFG 5 实测 1242 s（CFG>1 双倍前向）。
MASKCHECK_MINUTES = 0.3


@dataclass
class Scail2Request:
    project: str
    exp: str
    mode: str                      # maskcheck | full
    driving: Path
    ref: Path
    ref_extra: List[Path] = field(default_factory=list)
    prompt_file: Optional[Path] = None
    seed: int = 20260908
    length: Optional[int] = None   # 默认取驱动视频帧数
    width: Optional[int] = None
    height: Optional[int] = None
    sam3_word: str = "human"
    sam3_word_ref: Optional[str] = None
    steps: int = 6
    cfg: float = 1.0
    distill: float = 0.8
    dpo: float = 1.0
    pose_strength: float = 1.0
    pose_end: float = 1.0
    animation: bool = False        # 默认替换模式
    negative_extra: str = ""
    max_objects: int = 1
    gpu_hourly: float = 2.78

    @property
    def replacement(self):
        return not self.animation

    @property
    def experiment_dir(self):
        return paths.PROJECTS / self.project / "experiments" / self.exp


def estimate_minutes(request, length):
    if request.mode != "full":
        return MASKCHECK_MINUTES
    return (0.4 + 0.02 * length) * max(1.0, request.steps / 6) * (2.0 if request.cfg > 1.0 else 1.0)
