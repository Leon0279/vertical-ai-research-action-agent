"""Domain model for research_knowledge_memory tool results."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models.retrieval import (
    NormalizedRetrievalItem,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)

AcquisitionStatus = Literal["success", "partial_success", "no_result", "failed"]


class ResearchKnowledgeMemoryToolResult(BaseModel):
    """Normalized runtime output returned by the research_knowledge_memory tool."""

    normalized_items: list[NormalizedRetrievalItem] = Field(
        default_factory=list,
        description="Unified candidate material items for downstream evidence processing.",
    )
    acquisition_status: AcquisitionStatus = Field(
        description="Overall acquisition status for the tool execution.",
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description="Number of items dropped during adapter or tool-level normalization.",
    )
    source_summary: RetrievalSourceSummary = Field(
        default_factory=RetrievalSourceSummary,
        description="Summary of selected family/tool and normalized item counts.",
    )
    execution_summary: RetrievalExecutionSummary = Field(
        default_factory=RetrievalExecutionSummary,
        description="Execution-level counts and degradation signals for observability.",
    )
    retrieval_trace: RetrievalTrace = Field(
        default_factory=RetrievalTrace,
        description="Compact trace of recall inputs and returned knowledge references.",
    )
    error_info: str | None = Field(
        default=None,
        description="Top-level failure explanation when acquisition_status is failed.",
    )
