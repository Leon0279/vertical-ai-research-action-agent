"""Private normalization helpers for tool-execution-layer requests."""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.enums import FamilyName


def normalize_family_list(families: Iterable[FamilyName]) -> list[FamilyName]:
    """将 family 列表标准化为保持输入顺序的唯一枚举值。"""

    normalized: list[FamilyName] = []
    seen: set[FamilyName] = set()
    for family in families:
        normalized_family = FamilyName(str(family).strip())
        if normalized_family in seen:
            continue
        normalized.append(normalized_family)
        seen.add(normalized_family)
    return normalized
