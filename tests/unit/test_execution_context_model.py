"""Execution context model tests."""

import pytest
from pydantic import ValidationError

from app.domain.models import (
    ContextItem,
    ExecutionContext,
    RunningState,
    RuntimeContext,
    SupplementalContext,
)


def test_running_state_defaults_follow_context_construction_lld() -> None:
    state = RunningState(original_query="Compare agent memory stores")

    assert state.task_type is None
    assert state.workflow_pattern is None
    assert state.execution_policy is None
    assert state.constraints == []
    assert state.plan == []
    assert state.retrieved_evidence_refs == []
    assert state.intermediate_findings == []
    assert state.action_items == []


def test_context_item_requires_directly_consumable_summary() -> None:
    with pytest.raises(ValidationError):
        ContextItem(id="ctx-1", source_type="session_memory", summary="", priority=10)


def test_supplemental_context_is_partitioned() -> None:
    item = ContextItem(
        id="ctx-1",
        source_type="decision_memory",
        summary="The project already chose Redis for session memory.",
        priority=10,
        usage_hint="planning_only",
    )

    context = SupplementalContext(decision_support=[item])

    assert context.session_support == []
    assert context.decision_support == [item]
    assert context.policy_support == []
    assert context.external_evidence_support == []


def test_execution_context_composes_required_runtime_objects() -> None:
    running_state = RunningState(original_query="Plan next research step")
    runtime_context = RuntimeContext(
        request_id="trace-1",
        user_id="user-1",
        session_id="session-1",
    )

    context = ExecutionContext(
        running_state=running_state,
        runtime_context=runtime_context,
    )

    assert context.running_state is running_state
    assert isinstance(context.supplemental_context, SupplementalContext)
    assert context.runtime_context is runtime_context
    assert context.runtime_context.available_tools == []


def test_runtime_context_carries_request_and_session_identity() -> None:
    runtime_context = RuntimeContext(
        request_id="trace-1",
        user_id="user-1",
        session_id="session-1",
        session_id_generated=True,
    )

    assert runtime_context.request_id == "trace-1"
    assert runtime_context.user_id == "user-1"
    assert runtime_context.session_id == "session-1"
    assert runtime_context.session_id_generated is True
    assert runtime_context.stage_history == []
