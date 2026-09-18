"""Public Decision Memory item response schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DecisionMemoryItemResponse(BaseModel):
    """公开一条 Decision Memory 的业务字段，不暴露内部治理信息。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    decision_id: str = Field(min_length=1)
    decision_title: str | None = None
    decision_question: str | None = None
    chosen_option: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    rationale: str | None = None
    tradeoffs: list[str] = Field(default_factory=list)
    decision_state: str | None = None
    impact_scope: str | None = None
    confidence: float | None = None
    decided_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    derived_from_session_id: str | None = None
    derived_from_run_id: str | None = None
    source_refs: list[str] = Field(default_factory=list)
