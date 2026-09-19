"""Project-scoped aggregate Memory overview."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.memory.memory_collection_summary import (
    MemoryCollectionSummary,
)


class MemorySummary(BaseModel):
    """Combine the default visible collections for one project context."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    project_profile: MemoryCollectionSummary
    decisions: MemoryCollectionSummary
    actions: MemoryCollectionSummary
    policies: MemoryCollectionSummary
    research_knowledge: MemoryCollectionSummary
