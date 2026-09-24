"""Workflow router service tests."""

from __future__ import annotations

import asyncio
import logging

import pytest

from app.domain.enums import TaskType, WorkflowPattern
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
    ("task_type", "workflow_pattern"),
    [
        (TaskType.TOPIC_EXPLORATION, WorkflowPattern.TOPIC_EXPLORATION),
        (TaskType.COMPARISON, WorkflowPattern.COMPARISON),
        (TaskType.RECOMMENDATION, WorkflowPattern.RECOMMENDATION),
        (TaskType.ACTION_PLANNING, WorkflowPattern.ACTION_PLANNING),
        (TaskType.TRACKING, WorkflowPattern.TRACKING),
    ],
)
def test_workflow_router_maps_supported_task_types(
    task_type: TaskType,
    workflow_pattern: WorkflowPattern,
) -> None:
    context = _context(task_type.value)

    asyncio.run(WorkflowRouterService().route(context))

    state = context.running_state
    assert state.task_type == task_type.value
    assert state.workflow_pattern == workflow_pattern


def test_workflow_router_falls_back_when_task_type_is_missing(caplog) -> None:
    caplog.set_level(logging.INFO)
    context = _context(None)

    asyncio.run(WorkflowRouterService().route(context))

    assert context.running_state.task_type == TaskType.TOPIC_EXPLORATION.value
    assert context.running_state.workflow_pattern == WorkflowPattern.TOPIC_EXPLORATION
    record = next(
        record
        for record in caplog.records
        if record.message == "Workflow route selected."
    )
    assert record.routing_confidence == "low"
    assert record.fallback_reason == (
        "Missing task_type; fell back to topic exploration workflow."
    )


def test_workflow_router_falls_back_when_task_type_is_invalid(caplog) -> None:
    caplog.set_level(logging.INFO)
    context = _context("UNSUPPORTED")

    asyncio.run(WorkflowRouterService().route(context))

    assert context.running_state.task_type == TaskType.TOPIC_EXPLORATION.value
    assert context.running_state.workflow_pattern == WorkflowPattern.TOPIC_EXPLORATION
    record = next(
        record
        for record in caplog.records
        if record.message == "Workflow route selected."
    )
    assert record.routing_confidence == "low"
    assert "Unsupported task_type" in record.fallback_reason
