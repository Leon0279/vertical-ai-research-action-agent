"""Intermediate finding models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IntermediateFinding(BaseModel):
    """表示研究过程中形成的中间发现。

Working conclusion produced during execution loop."""

    statement: str = Field(description="必填字段。研究执行过程中形成的中间判断或事实性发现，不是面向用户的最终答案。")
    rationale: str | None = Field(
        default=None,
        description="可选字段。该中间发现的证据依据、推导理由或适用范围；没有额外说明时为 None。",
    )
    confidence: float | None = Field(
        default=None,
        description="可选字段。该单条中间发现的可信度数值，不等同于最终答案的整体 confidence。",
    )
