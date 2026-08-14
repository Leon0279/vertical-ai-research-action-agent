"""Contract for task interpreter services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class TaskInterpreterProtocol(Protocol):
    """定义任务Interpreter的抽象交互契约。

Interprets a query into task-oriented state fields."""

    async def interpret(self, context: ExecutionContext) -> None:
        """Populate user-goal and task-type fields."""
