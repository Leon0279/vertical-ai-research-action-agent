"""Domain model for request completion and recovery evaluation requests."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models.families.base_family_execution_result import (
    BaseFamilyExecutionResult,
)
from app.domain.models.tool_execution_layer.retrieval_query_generation_request import (
    RetrievalFamily,
)

FailureReason = Literal[
    "timeout",
    "tool_error",
    "rate_limited",
    "malformed_response",
    "tool_unavailable",
    "auth_error",
    "invalid_request",
    "unknown_error",
]

FallbackPolicy = Literal[
    "no_fallback",
    "fallback_within_same_family",
    "fallback_to_broader_search",
]


class RequestCompletionEvaluationRequest(BaseModel):
    """Input for evaluating request completion and recovery need after one execution."""

    target_problem: str = Field(
        description="Current retrieval target problem for this execution round.",
    )
    selected_family: RetrievalFamily = Field(
        description="Family selected for the execution outcome being evaluated.",
    )
    generated_query: str | None = Field(
        default=None,
        description="Generated query used by the executed family, if available.",
    )
    execution_outcome: BaseFamilyExecutionResult = Field(
        description="Unified family execution outcome to evaluate.",
    )
    failure_reason: FailureReason | None = Field(
        default=None,
        description="Optional normalized failure reason when acquisition_status is failed.",
    )
    continuation_available: bool = Field(
        default=False,
        description="Whether the current request can continue without starting a new round.",
    )
    retry_budget: int = Field(
        default=1,
        description="Maximum allowed same-tool retries for this request.",
    )
    retry_count: int = Field(
        default=0,
        description="Retries already consumed for this request.",
    )
    fallback_policy: FallbackPolicy = Field(
        default="fallback_within_same_family",
        description="Recovery policy that controls same-family or broader fallback use.",
    )
    fallback_applied: bool = Field(
        default=False,
        description="Whether a fallback path has already been used in this request chain.",
    )
    max_results: int | None = Field(
        default=None,
        description="Optional upper bound for normalized items in this request.",
    )
    timeout_limit_ms: int | None = Field(
        default=None,
        description="Optional request-scoped timeout budget in milliseconds.",
    )
    request_elapsed_ms: int | None = Field(
        default=None,
        description="Elapsed milliseconds already consumed by the current request.",
    )
    available_families: list[RetrievalFamily] = Field(
        default_factory=list,
        description="Families currently available to the runtime for fallback.",
    )
    allowed_source_families: list[RetrievalFamily] = Field(
        default_factory=list,
        description="Optional allow-list restricting fallback families.",
    )
    blocked_source_families: list[RetrievalFamily] = Field(
        default_factory=list,
        description="Optional block-list removing fallback families from consideration.",
    )
