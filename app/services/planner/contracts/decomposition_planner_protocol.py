"""Contract for decomposition planner services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class DecompositionPlannerProtocol(Protocol):
    """定义拆解规划器的抽象交互契约。

Builds planning artifacts for the current run."""

    async def plan(self, context: ExecutionContext) -> None:
        """Populate planning fields when needed."""
