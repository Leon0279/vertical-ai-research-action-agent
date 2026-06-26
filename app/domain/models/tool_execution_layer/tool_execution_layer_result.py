"""Domain model for Tool Execution Layer results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.families.base_family_execution_result import (
    AcquisitionStatus,
)
from app.domain.models.tool_execution_layer.tool_execution_layer_request import (
    ExecutionStatus,
)


class ToolExecutionLayerResult(BaseModel):
    """Research Executor-facing output for one Tool Execution Layer request."""

    execution_status: ExecutionStatus = Field(
        description="Whether the layer flow completed or failed before final evaluation.",
    )
    normalized_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Final candidate materials returned by the executed family.",
    )
    acquisition_status: AcquisitionStatus = Field(
        description="Final acquisition status for this Tool Execution Layer request.",
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description="Final dropped item count from family execution.",
    )
    source_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Final source summary plus layer-level metadata.",
    )
    execution_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Layer-level execution summary.",
    )
    retrieval_trace: dict[str, Any] = Field(
        default_factory=dict,
        description="Layer-level retrieval trace for Research Executor continuity.",
    )
    error_info: str | None = Field(
        default=None,
        description="Failure explanation when execution_status is failed.",
    )
