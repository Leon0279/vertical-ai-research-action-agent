"""Paginated Action Memory query result."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.memory.action_memory_record import ActionMemoryRecord


class ActionMemoryPage(BaseModel):
    """表示一个项目范围内的一页 Action Memory。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    items: list[ActionMemoryRecord] = Field(default_factory=list)
    next_cursor: str | None = None
