"""prompt 文件顶部 YAML 风格 frontmatter 的解析。与具体引擎无关。

只支持本仓库用到的子集：标量、行内列表、行内映射、行尾注释。
用 JSON 而非 YAML 库是为了 Python 3.9 环境零依赖（见 docs/guide/PROJECT_SYSTEM.md）。
"""
import json
import re

from .errors import PromptError


def strip_comment(value):
    """去掉 YAML 风格的行尾注释（# 在引号外时）。"""
    quote = None
    for index, char in enumerate(value):
        if char in "'\"":
            quote = None if quote == char else (char if quote is None else quote)
        elif char == "#" and quote is None:
            return value[:index].rstrip()
    return value.strip()


def split_inline(value):
    """按顶层逗号切分行内列表/映射，忽略引号与括号内的逗号。"""
    parts, buf, quote, depth = [], [], None, 0
    for char in value:
        if char in "'\"":
            quote = None if quote == char else (char if quote is None else quote)
        elif quote is None and char in "[{":
            depth += 1
        elif quote is None and char in "]}":
            depth -= 1
        if char == "," and quote is None and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(char)
    if buf:
        parts.append("".join(buf).strip())
    return parts


def parse_scalar(raw):
    value = strip_comment(raw).strip()
    if not value:
        return ""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value.lower() in ("null", "none"):
        return None
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", value):
        return float(value) if "." in value else int(value)
    if value.startswith("[") and value.endswith("]"):
        return [parse_scalar(item) for item in split_inline(value[1:-1])]
    if value.startswith("{") and value.endswith("}"):
        result = {}
        for item in split_inline(value[1:-1]):
            if ":" not in item:
                raise PromptError(f"无法解析 frontmatter 映射：{value}")
            key, item_value = item.split(":", 1)
            result[key.strip().strip("'\"")] = parse_scalar(item_value)
        return result
    return value.strip("'\"")


def read(path):
    """返回 (frontmatter dict, 正文)；正文即送给模型的部分。"""
    text = path.read_text(encoding="utf-8")
    meta, body = {}, text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end < 0:
            raise PromptError(f"frontmatter 没有结束标记：{path}")
        lines = text[4:end].splitlines()
        index = 0
        while index < len(lines):
            line = lines[index]
            index += 1
            if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            if value.strip():
                meta[key.strip()] = parse_scalar(value)
                continue
            # 空值后面若跟着 "- " 行，按块列表收（YAML 里最常见的写法）。
            # 不支持块列表的旧实现会把 `references:` 静默丢成空串——那条路径太安静，容易假通过。
            items = []
            while index < len(lines) and lines[index].lstrip().startswith("- "):
                items.append(parse_scalar(lines[index].lstrip()[2:]))
                index += 1
            meta[key.strip()] = items if items else ""
        body = text[end + 5:].strip()
    return meta, body


def strip(text):
    return re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.S).strip()
