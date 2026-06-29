"""Domain model for Evidence Processing requests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.domain.models.families.base_family_execution_result import AcquisitionStatus
from app.domain.models.retrieval import (
    NormalizedRetrievalItem,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)

if TYPE_CHECKING:
    from app.domain.models.tool_execution_layer.tool_execution_layer_result import (
        ToolExecutionLayerResult,
    )


class EvidenceProcessingRequest(BaseModel):
    """Input for converting Tool Execution Layer outputs into evidence units."""

    normalized_items: list[NormalizedRetrievalItem] = Field(
        default_factory=list,
        description="Final candidate materials from the Tool Execution Layer.",
    )
    acquisition_status: AcquisitionStatus = Field(
        description="Final Tool Execution Layer acquisition status.",
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description="Item count dropped before evidence processing.",
    )
    source_summary: RetrievalSourceSummary = Field(
        default_factory=RetrievalSourceSummary,
        description="Tool Execution Layer source summary.",
    )
    execution_summary: RetrievalExecutionSummary = Field(
        default_factory=RetrievalExecutionSummary,
        description="Tool Execution Layer execution summary.",
    )
    retrieval_trace: RetrievalTrace = Field(
        default_factory=RetrievalTrace,
        description="Tool Execution Layer retrieval trace.",
    )

    @classmethod
    def from_tool_execution_result(
        cls,
        result: ToolExecutionLayerResult,
    ) -> "EvidenceProcessingRequest":
        """Build an evidence-processing request from TEL final output."""

        return cls(
            normalized_items=result.normalized_items,
            acquisition_status=result.acquisition_status,
            dropped_item_count=result.dropped_item_count,
            source_summary=result.source_summary,
            execution_summary=result.execution_summary,
            retrieval_trace=result.retrieval_trace,
        )
