"""通用 frontmatter 解析（与引擎无关）。"""
import pytest

from conftest import VALID_PROMPT
from t2v import frontmatter
from t2v.errors import PromptError


def test_scalar_parsing_handles_lists_maps_and_comments():
    assert frontmatter.parse_scalar("[@face, @character]") == ["@face", "@character"]
    assert frontmatter.parse_scalar("{depth: references/depth.mp4}") == {"depth": "references/depth.mp4"}
    assert frontmatter.parse_scalar("2.3              # H3 输出 56 帧") == 2.3
    assert frontmatter.parse_scalar('"none"') == "none"
    assert frontmatter.parse_scalar("true") is True
    assert frontmatter.parse_scalar("null") is None


def test_body_excludes_frontmatter(tmp_path):
    path = tmp_path / "shot.md"
    path.write_text(VALID_PROMPT, encoding="utf-8")
    meta, body = frontmatter.read(path)
    assert meta["duration"] == 3.0 and meta["status"] == "draft"
    assert body.startswith("subject_definitions:") and "version: v001" not in body


def test_file_without_frontmatter_is_returned_whole(tmp_path):
    path = tmp_path / "plain.md"
    path.write_text("just a prompt\n", encoding="utf-8")
    assert frontmatter.read(path) == ({}, "just a prompt\n")


def test_unterminated_frontmatter_is_rejected(tmp_path):
    broken = tmp_path / "broken.md"
    broken.write_text("---\nstatus: draft\n", encoding="utf-8")
    with pytest.raises(PromptError):
        frontmatter.read(broken)


def test_strip_removes_only_the_leading_block():
    assert frontmatter.strip(VALID_PROMPT).startswith("subject_definitions:")


def test_block_lists_are_read_as_lists(tmp_path):
    """`key:` 后面跟 `- 项` 的块列表要收成 list——旧实现会静默丢成空串，
    而生图 prompt 的 references 正是这么写的（丢了就等于没有参考图）。"""
    path = tmp_path / "p.md"
    path.write_text("---\nreferences:\n  - \"@a\"\n  - assets/canonical/b.png\nempty:\nstatus: draft\n---\nbody\n",
                    encoding="utf-8")
    meta, body = frontmatter.read(path)
    assert meta["references"] == ["@a", "assets/canonical/b.png"]
    assert meta["empty"] == ""
    assert meta["status"] == "draft"
    assert body == "body"
