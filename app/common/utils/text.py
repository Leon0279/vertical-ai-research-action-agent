"""Text normalization helpers shared across application layers."""

from __future__ import annotations

from collections.abc import Iterable


def strip_or_none(value: object) -> str | None:
    """去除可选文本首尾空白；空字符串统一表示为 ``None``。"""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def strip_optional_string(value: object) -> object:
    """保留非字符串验证输入，并将可选字符串裁剪为文本或 ``None``。"""

    if not isinstance(value, str):
        return value
    return strip_or_none(value)


def normalize_whitespace_or_none(value: object) -> str | None:
    """将字符串内部空白折叠为单个空格；非文本或空文本返回 ``None``。"""

    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized or None


def unique_non_empty_strings(values: Iterable[object]) -> list[str]:
    """返回去除空白和重复值后的稳定字符串列表。"""

    unique_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        unique_values.append(normalized)
        seen.add(normalized)
    return unique_values
