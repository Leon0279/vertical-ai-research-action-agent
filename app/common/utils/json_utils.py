"""JSON parsing and normalization helpers shared across application layers."""

from __future__ import annotations

import json
import re
from typing import Any


def strip_json_code_fence(
    value: str,
    *,
    allow_unterminated: bool = False,
    json_only: bool = False,
) -> str:
    """移除常见 Markdown JSON 代码围栏，并保留调用方的未闭合围栏策略。"""

    stripped = value.strip()
    if json_only:
        match = re.fullmatch(
            r"```(?:json)?\s*(.*?)\s*```",
            stripped,
            re.DOTALL | re.IGNORECASE,
        )
        return match.group(1).strip() if match else stripped
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if not lines or not lines[0].strip().startswith("```"):
        return stripped
    if lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    if allow_unterminated:
        return "\n".join(lines[1:]).strip()
    return stripped


def is_json_serializable(value: object) -> bool:
    """判断值能否被标准 JSON 编码。"""

    try:
        json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return False
    return True


def load_json_string_list(value: Any) -> list[str]:
    """将数据库返回的 JSON 数组值规范化为字符串列表。"""

    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise TypeError("Expected a JSON array.")
        return [str(item) for item in parsed]
    raise TypeError("Expected a list-like JSON field.")
