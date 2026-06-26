"""Domain model for Tool Execution Layer results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.families.base_family_execution_result import (
    AcquisitionStatus,
    BaseFamilyExecutionResult,
)
from app.domain.models.tool_execution_layer.family_selection_result import (
    FamilySelectionResult,
)
from app.domain.models.tool_execution_layer.request_completion_evaluation_result import (
    RequestCompletionEvaluationResult,
)
from app.domain.models.tool_execution_layer.retrieval_query_generation_result import (
    RetrievalQueryGenerationResult,
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
    selected_family: str | None = Field(
        default=None,
        description="Final selected family used by the layer flow.",
    )
    generated_query: str | None = Field(
        default=None,
        description="Final generated retrieval query used for family execution.",
    )
    query_focus: str | None = Field(
        default=None,
        description="Final generated query focus label.",
    )
    needs_recovery: bool = Field(
        default=False,
        description="Whether the final evaluation still indicates recovery need.",
    )
    next_step_hint: str | None = Field(
        default=None,
        description="Final evaluation next-step hint.",
    )
    family_selection_result: FamilySelectionResult | None = Field(
        default=None,
        description="Most recent family selection result.",
    )
    query_generation_result: RetrievalQueryGenerationResult | None = Field(
        default=None,
        description="Most recent query generation result.",
    )
    family_execution_result: BaseFamilyExecutionResult | None = Field(
        default=None,
        description="Most recent family execution result.",
    )
    completion_evaluation_result: RequestCompletionEvaluationResult | None = Field(
        default=None,
        description="Most recent completion evaluation result.",
    )
    recovery_attempt_count: int = Field(
        default=0,
        ge=0,
        description="Internal recovery attempts executed by the layer.",
    )
    fallback_applied: bool = Field(
        default=False,
        description="Whether a broader-family fallback was applied by the layer.",
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Total retry count after the layer flow.",
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
