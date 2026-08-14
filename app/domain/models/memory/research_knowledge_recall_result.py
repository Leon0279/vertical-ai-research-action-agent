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
        description="必填字段。被语义召回的完整 ResearchKnowledgeUnitRecord。",
    )
    relevance_score: float | None = Field(
        default=None,
        description="可选字段。由 pgvector 距离换算得到的相似度风格分数；store 未提供时为 None。",
    )
