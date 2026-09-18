"""H3 的 prompt 字段与输入校验（通用 frontmatter 解析见 test_frontmatter.py）。"""
from conftest import VALID_PROMPT
from t2v import frontmatter
from t2v.engines.h3 import prompt
from t2v.engines.h3.request import H3Request
from t2v.paths import ROOT


def make_request(tmp_path, text=VALID_PROMPT, **overrides):
    path = tmp_path / "shot.md"
    path.write_text(text, encoding="utf-8")
    meta, body = frontmatter.read(path)
    fields = dict(workflow=ROOT / "workflows/h3/r2v.api.json",
                  prompt_text=body, prompt_path=path, duration=3.0, meta=meta)
    fields.update(overrides)
    return H3Request(**fields)


def test_frame_buckets_follow_17k_plus_5():
    assert [prompt.expected_frames(x) for x in (3.0, 2.3, 4.46, 5.875)] == [73, 56, 107, 141]


def test_valid_prompt_passes(tmp_path):
    errors, warnings = prompt.validate_prompt(make_request(tmp_path))
    assert errors == []
    assert not any("退役" in warning for warning in warnings)


def test_missing_section_and_bad_status_are_errors(tmp_path):
    text = VALID_PROMPT.replace("non_diegetic_music:", "music:").replace("status: draft", "status: 待定")
    errors, _ = prompt.validate_prompt(make_request(tmp_path, text))
    assert any("non_diegetic_music" in error for error in errors)
    assert any("status" in error for error in errors)


def test_retired_control_keys_warn_but_do_not_fail(tmp_path):
    text = VALID_PROMPT.replace("status: draft", 'status: draft\ncontrol: "depth"\nguides: {0: a.png}')
    errors, warnings = prompt.validate_prompt(make_request(tmp_path, text))
    assert errors == []
    assert any("control" in warning and "退役" in warning for warning in warnings)


def test_missing_input_file_is_an_error(tmp_path):
    errors, _ = prompt.validate_prompt(make_request(tmp_path, workflow=tmp_path / "nope.api.json"))
    assert any("缺少输入" in error for error in errors)


def test_bad_retime_values_are_errors(tmp_path):
    errors, _ = prompt.validate_prompt(make_request(tmp_path, retime_output_frames=0))
    assert any("retime_output_frames" in error for error in errors)


def test_base_mode_checks_three_sections_not_six(tmp_path):
    """T2V / I2V 用官方 base 三段式；用六段式的标准去卡它们是校验器的错，不是 prompt 的错。"""
    base_text = VALID_PROMPT.replace("subject_definitions:", "integrated_multimodal_description:")
    request = make_request(tmp_path, base_text, mode="base")
    missing = [e for e in prompt.validate_prompt(request)[0] if "缺少" in e]
    assert missing == []
    # 同一份 prompt 按 r2v 校验就该报缺字段
    assert [e for e in prompt.validate_prompt(make_request(tmp_path, base_text))[0] if "缺少" in e]


def test_base_mode_has_no_word_range_because_the_official_guide_gives_none(tmp_path):
    long_text = VALID_PROMPT.replace("subject_definitions:", "integrated_multimodal_description:")
    warnings = prompt.validate_prompt(make_request(tmp_path, long_text, mode="base"))[1]
    assert not any("英文词" in w for w in warnings)


def test_mode_aliases_and_unknown_modes():
    assert prompt.normalize_mode("t2v") == prompt.normalize_mode("i2v") == "base"
    assert prompt.normalize_mode(None) == prompt.normalize_mode("r2v") == "r2v"
    import pytest
    from t2v.errors import PromptError
    with pytest.raises(PromptError, match="未知的 engine.mode"):
        prompt.normalize_mode("wan")


def test_i2v_without_a_first_frame_is_an_error(tmp_path):
    """engine.mode=i2v 却拿不到首帧，图生视频会悄悄退化成文生视频——这里必须拦下来。"""
    base_text = VALID_PROMPT.replace("subject_definitions:", "integrated_multimodal_description:")
    errors, _ = prompt.validate_prompt(make_request(tmp_path, base_text, mode="i2v"))
    assert any("first_frame" in error for error in errors)
    frame = tmp_path / "kf-01.png"
    frame.write_bytes(b"png")
    errors, _ = prompt.validate_prompt(make_request(tmp_path, base_text, mode="i2v", first_frame=frame))
    assert not any("first_frame" in error for error in errors)


def test_last_frame_modes_are_rejected_until_the_engine_wires_them(tmp_path):
    base_text = VALID_PROMPT.replace("subject_definitions:", "integrated_multimodal_description:")
    errors, _ = prompt.validate_prompt(make_request(tmp_path, base_text, mode="fl2v"))
    assert any("fl2v" in error and "first_frame" in error for error in errors)
