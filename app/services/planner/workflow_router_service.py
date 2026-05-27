"""Workflow routing skeleton implementation."""

from __future__ import annotations

from app.domain.enums.task_type import TaskType
from app.domain.enums.workflow_pattern import WorkflowPattern
from app.domain.models import ExecutionState
from app.services.planner.contracts.workflow_router_protocol import WorkflowRouterProtocol


class WorkflowRouterService(WorkflowRouterProtocol):
    """Route task types to workflow patterns."""

    async def route(self, state: ExecutionState) -> None:
        mapping = {
            TaskType.TOPIC_EXPLORATION: WorkflowPattern.TOPIC_EXPLORATION,
            TaskType.COMPARISON: WorkflowPattern.COMPARISON,
            TaskType.RECOMMENDATION: WorkflowPattern.RECOMMENDATION,
            TaskType.ACTION_PLANNING: WorkflowPattern.ACTION_PLANNING,
            TaskType.TRACKING: WorkflowPattern.TRACKING,
        }
        state.workflow_pattern = mapping[state.task_type or TaskType.TOPIC_EXPLORATION]
