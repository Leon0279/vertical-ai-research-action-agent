"""Contract for task interpreter services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionState


@runtime_checkable
class TaskInterpreterProtocol(Protocol):
    """Interprets a query into task-oriented state fields."""

    async def interpret(self, state: ExecutionState) -> None:
        """Populate user-goal and task-type fields."""
