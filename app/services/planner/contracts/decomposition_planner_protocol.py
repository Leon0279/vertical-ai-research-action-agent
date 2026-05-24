"""Contract for decomposition planner services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionState


@runtime_checkable
class DecompositionPlannerProtocol(Protocol):
    """Builds planning artifacts for the current run."""

    async def plan(self, state: ExecutionState) -> None:
        """Populate planning fields when needed."""
