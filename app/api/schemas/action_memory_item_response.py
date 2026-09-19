"""Public Action Memory item response schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.memory.action_memory_status import ActionMemoryStatus


class ActionMemoryItemResponse(BaseModel):
    """公开一条 Action Memory 的业务字段，不暴露内部治理信息。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    action_id: str = Field(min_length=1)
    parent_decision_id: str | None = None
    action_title: str | None = None
    action_description: str | None = None
    action_status: ActionMemoryStatus
    priority: str | None = None
    owner: str | None = None
    due_at: datetime | None = None
    blocking_reason: str | None = None
    result_summary: str | None = None
    completed_at: datetime | None = None
    confidence: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    derived_from_session_id: str | None = None
    derived_from_run_id: str | None = None
    source_refs: list[str] = Field(default_factory=list)
