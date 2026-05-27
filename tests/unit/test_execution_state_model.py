"""Execution state model tests."""

from app.domain.models import ExecutionState


def test_execution_state_defaults() -> None:
    state = ExecutionState(original_query="What is agentic retrieval?")
    assert state.user_goal is None
    assert state.stage_history == []
    assert state.request_metadata == {}
    assert state.retrieved_evidence == []
    assert state.memory_candidates == []
