"""Execution context model tests."""

import pytest
from pydantic import ValidationError

from app.domain.enums import FamilyName, PlanningDepth
from app.domain.models import (
    ContextItem,
    ExecutionContext,
    RunningState,
    RuntimeContext,
    SourceReference,
    SupplementalContext,
)


def test_running_state_defaults_follow_context_construction_lld() -> None:
    state = RunningState(original_query="Compare agent memory stores")

    assert state.task_type is None
    assert state.workflow_pattern is None
    assert state.execution_policy is None
    assert state.constraints == []
    assert state.planning_depth == PlanningDepth.NONE
    assert state.plan == []
    assert state.initial_evidence_strategy == []
    assert state.retrieved_evidence_refs == []
    assert state.intermediate_findings == []
    assert state.research_status is None
    assert state.research_iteration_count == 0
    assert state.final_answer is None
    assert state.final_summary is None
    assert state.final_recommendation is None
    assert state.action_items == []
    assert state.citations == []
    assert state.confidence is None
    assert state.caveats == []


def test_running_state_uses_typed_retrieved_evidence_refs() -> None:
    reference = SourceReference(
        source_type="paper",
        source_id="2501.12345v2",
        source_id_type="arxiv_id",
    )

    state = RunningState(
        original_query="Compare agent memory stores",
        retrieved_evidence_refs=[reference],
    )

    assert state.retrieved_evidence_refs == [reference]
    assert state.model_dump(mode="json")["retrieved_evidence_refs"][0]["source_id"] == (
        "2501.12345v2"
    )


def test_running_state_rejects_legacy_string_retrieved_evidence_refs() -> None:
    with pytest.raises(ValidationError):
        RunningState(
            original_query="Compare agent memory stores",
            retrieved_evidence_refs=["ref-1"],
        )


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
    assert context.runtime_context.available_families == []


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


def test_runtime_context_uses_retrieval_family_enum() -> None:
    runtime_context = RuntimeContext(
        request_id="trace-1",
        user_id="user-1",
        session_id="session-1",
        available_families=[FamilyName.DOCS_SEARCH],
    )

    assert runtime_context.available_families == [FamilyName.DOCS_SEARCH]
    assert runtime_context.model_dump(mode="json")["available_families"] == [
        "docs_search"
    ]

    with pytest.raises(ValidationError):
        RuntimeContext(
            request_id="trace-1",
            user_id="user-1",
            session_id="session-1",
            available_families=["llms_txt_docs_search_v1"],
        )
