"""Contract for request completion and recovery evaluation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    RequestCompletionEvaluationRequest,
    RequestCompletionEvaluationResult,
)


@runtime_checkable
class RequestCompletionEvaluationServiceProtocol(Protocol):
    """Runtime-facing interface for request completion and recovery evaluation."""

    async def evaluate(
        self,
        request: RequestCompletionEvaluationRequest,
    ) -> RequestCompletionEvaluationResult:
        """Evaluate whether the current retrieval request is complete or needs recovery."""
