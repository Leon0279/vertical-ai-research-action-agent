"""Contract for workflow router services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionContext


@runtime_checkable
class WorkflowRouterProtocol(Protocol):
    """定义工作流路由器的抽象交互契约。

Routes a task into a workflow pattern."""

    async def route(self, context: ExecutionContext) -> None:
        """Populate workflow pattern based on task type."""
