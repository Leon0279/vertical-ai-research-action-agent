"""Paginated Research Knowledge Memory query result."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.memory.research_knowledge_unit_record import (
    ResearchKnowledgeUnitRecord,
)


class ResearchKnowledgeMemoryPage(BaseModel):
    """表示一个项目上下文内的一页可浏览 Research Knowledge。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    items: list[ResearchKnowledgeUnitRecord] = Field(default_factory=list)
    next_cursor: str | None = None
