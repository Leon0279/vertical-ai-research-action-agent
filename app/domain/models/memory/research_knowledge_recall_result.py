"""Result object for research knowledge semantic recall."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.memory.research_knowledge_unit_record import (
    ResearchKnowledgeUnitRecord,
)


class ResearchKnowledgeRecallResult(BaseModel):
    """A recalled knowledge unit plus its adapter-level semantic relevance score."""

    model_config = ConfigDict(extra="forbid")

    unit: ResearchKnowledgeUnitRecord = Field(
        description="Recalled research knowledge unit.",
    )
    relevance_score: float | None = Field(
        default=None,
        description="Similarity-style score derived from pgvector distance.",
    )
