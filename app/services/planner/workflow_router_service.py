"""Workflow routing implementation."""

from __future__ import annotations

import logging

from app.domain.enums import TaskType, WorkflowPattern
from app.domain.models import ExecutionContext
from app.services.planner.contracts.workflow_router_protocol import WorkflowRouterProtocol

logger = logging.getLogger(__name__)


class WorkflowRouterService(WorkflowRouterProtocol):
    """负责处理工作流路由器相关业务逻辑的服务。

Route interpreted task types to workflow patterns."""

    _TASK_TO_WORKFLOW = {
        TaskType.TOPIC_EXPLORATION: WorkflowPattern.TOPIC_EXPLORATION,
        TaskType.COMPARISON: WorkflowPattern.COMPARISON,
        TaskType.RECOMMENDATION: WorkflowPattern.RECOMMENDATION,
        TaskType.ACTION_PLANNING: WorkflowPattern.ACTION_PLANNING,
        TaskType.TRACKING: WorkflowPattern.TRACKING,
    }

    async def route(self, context: ExecutionContext) -> None:
        state = context.running_state
        task_type, fallback_reason = self._task_type_from_state(state.task_type)
        state.task_type = task_type.value
        state.workflow_pattern = self._TASK_TO_WORKFLOW[task_type]
        logger.info(
            "Workflow route selected.",
            extra={
                "task_type": state.task_type,
                "workflow_pattern": state.workflow_pattern.value,
                "routing_confidence": "low" if fallback_reason else "high",
                "fallback_reason": fallback_reason,
                "project_scope_id": state.project_scope_id,
                "has_project_context": state.project_context_summary is not None,
                "constraint_count": len(state.constraints),
            },
        )

    def _task_type_from_state(self, task_type: str | None) -> tuple[TaskType, str | None]:
        if not task_type:
            return (
                TaskType.TOPIC_EXPLORATION,
                "Missing task_type; fell back to topic exploration workflow.",
            )
        try:
            return TaskType(task_type), None
        except ValueError:
            return (
                TaskType.TOPIC_EXPLORATION,
                f"Unsupported task_type {task_type!r}; fell back to topic exploration workflow.",
            )
