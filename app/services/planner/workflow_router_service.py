"""Workflow routing implementation."""

from __future__ import annotations

import logging

from app.domain.enums import MemoryType, PlanningDepth, TaskType, WorkflowPattern
from app.domain.models import ExecutionContext, WorkflowExecutionPolicy
from app.services.planner.contracts.workflow_router_protocol import WorkflowRouterProtocol

logger = logging.getLogger(__name__)


class WorkflowRouterService(WorkflowRouterProtocol):
    """负责处理工作流路由器相关业务逻辑的服务。

Route interpreted task types to workflow patterns and execution policies."""

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
        state.execution_policy = self._execution_policy_for(
            task_type=task_type,
            fallback_reason=fallback_reason,
        )
        logger.info(
            "Workflow route selected.",
            extra={
                "task_type": state.task_type,
                "workflow_pattern": state.workflow_pattern.value,
                "routing_confidence": state.execution_policy.routing_confidence,
                "fallback_reason": state.execution_policy.fallback_reason,
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

    def _execution_policy_for(
        self,
        *,
        task_type: TaskType,
        fallback_reason: str | None,
    ) -> WorkflowExecutionPolicy:
        routing_confidence = "low" if fallback_reason else "high"
        if task_type == TaskType.TOPIC_EXPLORATION:
            return WorkflowExecutionPolicy(
                planning_depth=PlanningDepth.SHALLOW,
                evidence_strategy="conceptual_research",
                output_emphasis="topic_overview",
                memory_writeback_focus=[MemoryType.RESEARCH_KNOWLEDGE],
                routing_confidence=routing_confidence,
                fallback_reason=fallback_reason,
            )
        if task_type == TaskType.COMPARISON:
            return WorkflowExecutionPolicy(
                planning_depth=PlanningDepth.MEDIUM,
                evidence_strategy="comparative_evidence",
                output_emphasis="comparison",
                memory_writeback_focus=[MemoryType.RESEARCH_KNOWLEDGE],
                comparison_needed=True,
                routing_confidence=routing_confidence,
                fallback_reason=fallback_reason,
            )
        if task_type == TaskType.RECOMMENDATION:
            return WorkflowExecutionPolicy(
                planning_depth=PlanningDepth.MEDIUM,
                evidence_strategy="decision_support",
                output_emphasis="recommendation",
                memory_writeback_focus=[MemoryType.DECISION, MemoryType.ACTION_EXECUTION],
                comparison_needed=True,
                recommendation_needed=True,
                action_generation_needed=True,
                routing_confidence=routing_confidence,
                fallback_reason=fallback_reason,
            )
        if task_type == TaskType.ACTION_PLANNING:
            return WorkflowExecutionPolicy(
                planning_depth=PlanningDepth.MEDIUM,
                evidence_strategy="execution_planning",
                output_emphasis="action_plan",
                memory_writeback_focus=[MemoryType.ACTION_EXECUTION],
                action_generation_needed=True,
                routing_confidence=routing_confidence,
                fallback_reason=fallback_reason,
            )
        return WorkflowExecutionPolicy(
            planning_depth=PlanningDepth.SHALLOW,
            evidence_strategy="update_tracking",
            output_emphasis="status_update",
            memory_writeback_focus=[MemoryType.TRACKING_WATCHLIST],
            tracking_needed=True,
            routing_confidence=routing_confidence,
            fallback_reason=fallback_reason,
        )
