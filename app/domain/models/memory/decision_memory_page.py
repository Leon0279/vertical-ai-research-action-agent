"""Paginated Decision Memory query result."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.memory.decision_memory_record import DecisionMemoryRecord


class DecisionMemoryPage(BaseModel):
    """表示一个项目范围内的一页 active Decision Memory。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    items: list[DecisionMemoryRecord] = Field(default_factory=list)
    next_cursor: str | None = None
