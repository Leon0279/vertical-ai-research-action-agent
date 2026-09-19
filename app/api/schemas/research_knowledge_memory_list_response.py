"""Public paginated Research Knowledge Memory response."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.research_knowledge_memory_item_response import (
    ResearchKnowledgeMemoryItemResponse,
)


class ResearchKnowledgeMemoryListResponse(BaseModel):
    """Return one page of knowledge visible from a project context."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    items: list[ResearchKnowledgeMemoryItemResponse] = Field(default_factory=list)
    next_cursor: str | None = None
