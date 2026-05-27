"""Contract for request intake services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionState, RequestContext


@runtime_checkable
class RequestIntakeProtocol(Protocol):
    """Build the initial execution state from an incoming request."""

    async def intake(self, request: RequestContext) -> ExecutionState:
        """Normalize an incoming request into the canonical run state."""
