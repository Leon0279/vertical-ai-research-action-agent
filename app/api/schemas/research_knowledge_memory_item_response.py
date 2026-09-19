"""Public Research Knowledge Memory response item."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.memory.research_knowledge_visibility_scope import (
    ResearchKnowledgeVisibilityScope,
)
from app.domain.models.source import SourceReference


class ResearchKnowledgeMemoryItemResponse(BaseModel):
    """Expose reusable knowledge while hiding ownership and governance internals."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    knowledge_id: str = Field(min_length=1)
    visibility_scope: ResearchKnowledgeVisibilityScope
    visibility_scope_effective: ResearchKnowledgeVisibilityScope
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    knowledge_type: str = Field(min_length=1)
    topic_tags: list[str] = Field(default_factory=list)
    confidence: float | None = None
    source_refs: list[SourceReference] = Field(default_factory=list)
    source_type: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    freshness_sensitivity: Literal["low", "medium", "high"] | None = None
    freshness_status: Literal["fresh", "aging", "stale"] | None = None
    last_verified_at: datetime | None = None
    freshness_checked_at: datetime | None = None
    staleness_reason: str | None = None
    derived_from_session_id: str | None = None
    derived_from_run_id: str | None = None
