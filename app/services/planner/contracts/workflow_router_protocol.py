"""Contract for workflow router services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionState


@runtime_checkable
class WorkflowRouterProtocol(Protocol):
    """Routes a task into a workflow pattern."""

    async def route(self, state: ExecutionState) -> None:
        """Populate workflow pattern based on task type."""
