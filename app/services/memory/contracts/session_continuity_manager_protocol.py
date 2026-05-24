"""Contract for session continuity services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionState


@runtime_checkable
class SessionContinuityManagerProtocol(Protocol):
    """Persists continuity fields for follow-up turns."""

    async def update(self, state: ExecutionState) -> None:
        """Persist task-relevant continuity fields."""
