"""Domain model for request completion and recovery evaluation results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EvaluationStatus = Literal["evaluated", "failed"]
RequestCompletionStatus = Literal[
    "complete",
    "incomplete_recoverable",
    "incomplete_unrecoverable",
]
RecoveryAction = Literal["continue", "retry_same_tool", "fallback", "stop"]
NextStepHint = Literal[
    "none",
    "continue_current_request",
    "retry_same_tool",
    "fallback_within_same_family",
    "fallback_to_broader_search",
    "stop_request",
]


class RequestCompletionEvaluationResult(BaseModel):
    """Output of evaluating request completion and recovery need."""

    evaluation_status: EvaluationStatus = Field(
        description="Whether evaluation completed successfully or failed due to bad input.",
    )
    request_completion_status: RequestCompletionStatus | None = Field(
        default=None,
        description="Whether the request is complete, recoverable, or unrecoverable.",
    )
    request_completed: bool = Field(
        description="Whether the current request should be considered complete.",
    )
    needs_recovery: bool = Field(
        description="Whether a recovery path should be considered by downstream orchestration.",
    )
    recovery_action: RecoveryAction | None = Field(
        default=None,
        description="Minimal recovery action signal; never a direct execution command.",
    )
    recovery_reason: str | None = Field(
        default=None,
        description="Human-readable explanation for the recovery or stop decision.",
    )
    next_step_hint: NextStepHint | None = Field(
        default=None,
        description="Compact hint for the next orchestration step.",
    )
    evaluation_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Compact summary of evaluation outcome and policy.",
    )
    evaluation_trace: dict[str, Any] = Field(
        default_factory=dict,
        description="Trace of normalized inputs and computed recovery availability.",
    )
    error_info: str | None = Field(
        default=None,
        description="Top-level evaluation failure explanation when evaluation_status is failed.",
    )
