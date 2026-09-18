"""H3 prompt 的字段与帧数校验。通用的 frontmatter 解析在 t2v/frontmatter.py。"""
import re

from ...errors import PromptError

# H3 有两套 prompt 结构，由 project.json 的 engine.mode 选择（官方 base 指南 / ref 指南）：
#   base —— T2V / I2V / 首尾帧，三段式
#   r2v  —— 参考图生视频，六段式
MODE_SECTIONS = {
    "base": ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music"),
    "r2v": ("subject_definitions", "summary", "retention_analysis",
            "detailed_description", "overall_soundscape", "non_diegetic_music"),
    # freeform：正文不按 H3 官方字段组织（例如照搬其它模型的分镜 prompt 格式）。
    # 只校验 status / 输入文件 / 重定时，字段与词数一概不管——用它就等于放弃这层保护。
    "freeform": (),
}
MODE_ALIASES = {"t2v": "base", "i2v": "base", "fl2v": "base", "l2v": "base"}
# 关键帧模式。引擎只接线了 first_frame（MiniMaxH3ImageToVideo.first_frame），没有 last_frame 输入，
# 所以 fl2v / l2v 不能靠写个 mode 就悄悄退化成 T2V；i2v 则必须有首帧，否则同样会退化成 T2V。
# 注意这与已退役的 `guides`（深度/姿态控制的关键帧锚点）不是一回事：那是控制节点，这是原生 I2V。
KEYFRAME_MODES = ("i2v", "fl2v", "l2v")
UNSUPPORTED_KEYFRAME_MODES = ("fl2v", "l2v")
DEFAULT_MODE = "r2v"
# 深度/姿态控制与关键帧锚点已于 2026-09-16 退役（见 docs/research/CAMERA_REPLICATION.md）；
# 旧 prompt 里这些键会被忽略，校验时提醒一次，避免被当成还生效的开关抄进新版本。
RETIRED_KEYS = ("control", "control_videos", "control_strength", "control_start", "control_end", "guides")
# 只有 ref 指南给了词数区间（detailed_description 350–500）；base 指南没规定，就不编。
WORD_RANGE = (350, 500)
# 中文正文按字符判定：官方规范只规定英文词数，中文没有对应区间，不套用。
CJK = re.compile(r"[\u4e00-\u9fff]")


def expected_frames(duration):
    """H3 的帧数桶：24 fps 下取最接近的 17k+5。"""
    frames = max(5, round(float(duration) * 24))
    return frames + (5 - frames % 17) % 17


def normalize_mode(value):
    """把 project.json 的 engine.mode 归一成 base / r2v。"""
    mode = (value or DEFAULT_MODE).lower()
    mode = MODE_ALIASES.get(mode, mode)
    if mode not in MODE_SECTIONS:
        raise PromptError(f"未知的 engine.mode {value!r}；可用：{', '.join(sorted(MODE_SECTIONS))}"
                          f"（别名 {', '.join(sorted(MODE_ALIASES))}）")
    return mode


def validate_prompt(request):
    """返回 (errors, warnings)。只做本机可查的事：字段、词数、输入文件是否存在。"""
    errors, warnings = [], []
    path, body, meta = request.prompt_path, request.prompt_text, request.meta
    mode = normalize_mode(request.mode)
    for section in MODE_SECTIONS[mode]:
        if not re.search(rf"(?m)^{re.escape(section)}:\s*", body):
            errors.append(f"{path}: 缺少 H3 {mode} 字段 {section}")
    keyframe_mode = (request.mode or "").lower()
    if keyframe_mode in UNSUPPORTED_KEYFRAME_MODES:
        errors.append(f"{path}: engine.mode={keyframe_mode} 需要末帧输入，H3 引擎目前只接线了 first_frame")
    elif keyframe_mode == "i2v" and request.first_frame is None:
        errors.append(f"{path}: engine.mode=i2v 缺少首帧——在 prompt frontmatter 写 "
                      f"first_frame: \"@别名\"，或在 project.json 的 defaults.first_frame 给默认值")
    match = re.search(r"(?ms)^detailed_description:\s*(.*?)(?=^overall_soundscape:)", body)
    if mode == "r2v" and match:
        body = match.group(1)
        # 官方只给了英文的词数区间；中文正文没有对应规定，不编一个假的区间来报警。
        if len(CJK.findall(body)) > len(body) / 4:
            pass
        else:
            words = len(re.findall(r"\b[\w'-]+\b", body))
            if not WORD_RANGE[0] <= words <= WORD_RANGE[1]:
                warnings.append(f"{path}: detailed_description 为 {words} 个英文词，官方建议 {WORD_RANGE[0]}–{WORD_RANGE[1]}")
    if meta.get("status") not in ("draft", "reviewed", "validated", "final"):
        errors.append(f"{path}: status 必须是 draft/reviewed/validated/final")
    if request.retime_output_frames is not None:
        if not isinstance(request.retime_output_frames, int) or request.retime_output_frames <= 0:
            errors.append(f"{path}: retime_output_frames 必须是正整数")
        if not isinstance(request.retime_fps, (int, float)) or request.retime_fps <= 0:
            errors.append(f"{path}: retime_fps 必须是正数")
    for value in request.input_paths():
        if not value.is_file():
            errors.append(f"缺少输入：{value}")
    retired = [key for key in RETIRED_KEYS if key in meta]
    if retired:
        warnings.append(f"{path}: frontmatter 里的 {', '.join(retired)} 已退役，会被忽略"
                        f"（深度/姿态控制与关键帧锚点已移除，当前是无控制 R2V）")
    return errors, warnings
