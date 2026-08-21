"""Shared service-layer confidence normalization."""

from __future__ import annotations


def confidence_to_score(confidence: str | None) -> float | None:
    """将 low、medium、high 置信度标签映射为统一分数。"""

    if confidence is None:
        return None
    return {"low": 0.2, "medium": 0.5, "high": 0.8}.get(confidence.lower())
