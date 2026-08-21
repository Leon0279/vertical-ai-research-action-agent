"""Small parsing helpers with conservative failure handling."""

from __future__ import annotations

from datetime import datetime


def parse_optional_iso_datetime(value: object) -> datetime | None:
    """解析可选 ISO 8601 时间字符串；无效值返回 ``None``。"""

    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        return None
