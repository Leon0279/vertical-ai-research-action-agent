"""Workflow router service tests."""

from __future__ import annotations

import asyncio

import pytest

from app.domain.enums import MemoryType, PlanningDepth, TaskType, WorkflowPattern
from app.domain.models import ExecutionContext, RunningState, RuntimeContext
from app.services.planner.workflow_router_service import WorkflowRouterService


def _context(task_type: str | None) -> ExecutionContext:
    return ExecutionContext(
        running_state=RunningState(
            original_query="Compare retrieval options.",
            task_type=task_type,
            user_goal="Choose a retrieval direction.",
            project_scope_id="project-1",
            project_context_summary="The project is in MVP stage.",
            constraints=["single developer"],
        ),
        runtime_context=RuntimeContext(
            request_id="run-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )


@pytest.mark.parametrize(
    (
        "task_type",
        "workflow_pattern",
        "planning_depth",
        "evidence_strategy",
        "output_emphasis",
        "memory_writeback_focus",
    ),
    [
        (
            TaskType.TOPIC_EXPLORATION,
            WorkflowPattern.TOPIC_EXPLORATION,
            PlanningDepth.SHALLOW,
            "conceptual_research",
            "topic_overview",
            [MemoryType.RESEARCH_KNOWLEDGE],
        ),
        (
            TaskType.COMPARISON,
            WorkflowPattern.COMPARISON,
            PlanningDepth.MEDIUM,
            "comparative_evidence",
            "comparison",
            [MemoryType.RESEARCH_KNOWLEDGE],
        ),
        (
            TaskType.RECOMMENDATION,
            WorkflowPattern.RECOMMENDATION,
            PlanningDepth.MEDIUM,
            "decision_support",
            "recommendation",
            [MemoryType.DECISION, MemoryType.ACTION_EXECUTION],
        ),
        (
            TaskType.ACTION_PLANNING,
            WorkflowPattern.ACTION_PLANNING,
            PlanningDepth.MEDIUM,
            "execution_planning",
            "action_plan",
            [MemoryType.ACTION_EXECUTION],
        ),
        (
            TaskType.TRACKING,
            WorkflowPattern.TRACKING,
            PlanningDepth.SHALLOW,
            "update_tracking",
            "status_update",
            [MemoryType.TRACKING_WATCHLIST],
        ),
    ],
)
def test_workflow_router_maps_supported_task_types(
    task_type: TaskType,
    workflow_pattern: WorkflowPattern,
    planning_depth: PlanningDepth,
    evidence_strategy: str,
    output_emphasis: str,
    memory_writeback_focus: list[MemoryType],
) -> None:
    context = _context(task_type.value)

    asyncio.run(WorkflowRouterService().route(context))

    state = context.running_state
    assert state.task_type == task_type.value
    assert state.workflow_pattern == workflow_pattern
    assert state.execution_policy is not None
    assert state.execution_policy.planning_depth == planning_depth
    assert state.execution_policy.evidence_strategy == evidence_strategy
    assert state.execution_policy.output_emphasis == output_emphasis
    assert state.execution_policy.memory_writeback_focus == memory_writeback_focus
    assert state.execution_policy.routing_confidence == "high"
    assert state.execution_policy.fallback_reason is None


def test_workflow_router_sets_recommendation_policy_flags() -> None:
    context = _context(TaskType.RECOMMENDATION.value)

    asyncio.run(WorkflowRouterService().route(context))

    policy = context.running_state.execution_policy
    assert policy is not None
    assert policy.comparison_needed is True
    assert policy.recommendation_needed is True
    assert policy.action_generation_needed is True
    assert policy.tracking_needed is False


def test_workflow_router_sets_tracking_policy_flag() -> None:
    context = _context(TaskType.TRACKING.value)

    asyncio.run(WorkflowRouterService().route(context))

    policy = context.running_state.execution_policy
    assert policy is not None
    assert policy.tracking_needed is True
    assert policy.comparison_needed is False


def test_workflow_router_falls_back_when_task_type_is_missing() -> None:
    context = _context(None)

    asyncio.run(WorkflowRouterService().route(context))

    policy = context.running_state.execution_policy
    assert context.running_state.task_type == TaskType.TOPIC_EXPLORATION.value
    assert context.running_state.workflow_pattern == WorkflowPattern.TOPIC_EXPLORATION
    assert policy is not None
    assert policy.routing_confidence == "low"
    assert policy.fallback_reason == "Missing task_type; fell back to topic exploration workflow."


def test_workflow_router_falls_back_when_task_type_is_invalid() -> None:
    context = _context("UNSUPPORTED")

    asyncio.run(WorkflowRouterService().route(context))

    policy = context.running_state.execution_policy
    assert context.running_state.task_type == TaskType.TOPIC_EXPLORATION.value
    assert context.running_state.workflow_pattern == WorkflowPattern.TOPIC_EXPLORATION
    assert policy is not None
    assert policy.routing_confidence == "low"
    assert "Unsupported task_type" in (policy.fallback_reason or "")
