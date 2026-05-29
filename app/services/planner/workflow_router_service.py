"""Workflow routing skeleton implementation."""

from __future__ import annotations

from app.domain.enums.task_type import TaskType
from app.domain.models import ExecutionContext
from app.services.planner.contracts.workflow_router_protocol import WorkflowRouterProtocol


class WorkflowRouterService(WorkflowRouterProtocol):
    """Route task types to workflow patterns."""

    async def route(self, context: ExecutionContext) -> None:
        state = context.running_state
        state.task_type = state.task_type or TaskType.TOPIC_EXPLORATION.value
