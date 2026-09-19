"""Paginated Policy Memory query result."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.memory.preference_policy_memory_record import (
    PreferencePolicyMemoryRecord,
)


class PolicyMemoryPage(BaseModel):
    """表示一个项目上下文内的一页 active Policy Memory。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    items: list[PreferencePolicyMemoryRecord] = Field(default_factory=list)
    next_cursor: str | None = None
