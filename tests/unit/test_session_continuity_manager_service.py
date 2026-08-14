"""Tests for deterministic session continuity rolling updates."""

import asyncio

from app.domain.models import (
    ExecutionContext,
    RunningState,
    RuntimeContext,
    SessionMemory,
    SessionTurnSummary,
)
from app.services.memory.session_continuity_manager_service import (
    SessionContinuityManagerService,
)


class _RecordingSessionStore:
    def __init__(
        self,
        loaded_memory: SessionMemory | None = None,
        *,
        load_error: Exception | None = None,
        save_error: Exception | None = None,
    ) -> None:
        self.loaded_memory = loaded_memory
        self.load_error = load_error
        self.save_error = save_error
        self.load_calls: list[tuple[str, str | None]] = []
        self.saved_memory: SessionMemory | None = None

    async def load(self, *, user_id: str, session_id: str | None) -> SessionMemory | None:
        self.load_calls.append((user_id, session_id))
        if self.load_error:
            raise self.load_error
        return self.loaded_memory

    async def save(self, memory: SessionMemory) -> None:
        if self.save_error:
            raise self.save_error
        self.saved_memory = memory


def _context(**state_updates: object) -> ExecutionContext:
    state = RunningState(
        original_query="Compare retrieval approaches.",
        user_goal="Choose a retrieval approach.",
        task_type="COMPARISON",
        **state_updates,
    )
    return ExecutionContext(
        running_state=state,
        runtime_context=RuntimeContext(
            request_id="run-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )


def test_update_creates_bounded_memory_from_current_run() -> None:
    store = _RecordingSessionStore()
    context = _context(
        task_framing="Compare the options for this project.",
        final_summary="The simpler baseline is the best first experiment.",
        final_answer="A longer user-facing answer.",
        final_recommendation="Start with the simpler baseline.",
        action_items=["Run a small evaluation.", "Run a small evaluation."],
        open_questions=["Which corpus should be used?"],
        project_scope_id="project-1",
        project_context_summary="A constrained internal search project.",
        constraints=["Prefer low operational cost."],
        current_bottleneck_summary="Evaluation data is still limited.",
    )

    asyncio.run(SessionContinuityManagerService(store).update(context))

    memory = store.saved_memory
    assert memory is not None
    assert "The simpler baseline is the best first experiment." in (
        memory.session_working_summary or ""
    )
    assert memory.latest_recommendation == "Start with the simpler baseline."
    assert memory.latest_action_items == ["Run a small evaluation."]
    assert memory.open_questions == ["Which corpus should be used?"]
    assert len(memory.recent_turn_summaries) == 1
    assert memory.recent_turn_summaries[0].role == "assistant"
    assert memory.recent_turn_summaries[0].content_summary == (
        "The simpler baseline is the best first experiment."
    )
    assert memory.temporary_context == {
        "project_scope_id": "project-1",
        "project_context_summary": "A constrained internal search project.",
        "constraints": ["Prefer low operational cost."],
        "current_bottleneck_summary": "Evaluation data is still limited.",
    }


def test_update_refreshes_authoritative_lists_and_preserves_missing_scalar_values() -> None:
    existing = SessionMemory(
        user_id="user-1",
        session_id="session-1",
        session_working_summary="Old working summary.",
        recent_turn_summaries=[
            SessionTurnSummary(role="assistant", content_summary="Older turn."),
        ],
        latest_recommendation="Keep the old recommendation.",
        latest_action_items=["Old action."],
        open_questions=["Old question."],
        current_local_task_framing="Old framing.",
        temporary_context={"legacy_debug": "must be removed"},
    )
    store = _RecordingSessionStore(existing)
    context = _context(action_items=[], open_questions=[])

    asyncio.run(SessionContinuityManagerService(store).update(context))

    memory = store.saved_memory
    assert memory is not None
    assert memory.latest_recommendation == "Keep the old recommendation."
    assert memory.current_local_task_framing == "Old framing."
    assert memory.latest_action_items == []
    assert memory.open_questions == []
    assert memory.temporary_context == {}
    assert len(memory.recent_turn_summaries) == 1
    assert memory.recent_turn_summaries[0].content_summary == "Older turn."


def test_update_applies_size_limits_and_deduplicates_values() -> None:
    store = _RecordingSessionStore()
    context = _context(
        final_summary="s" * 2500,
        action_items=[f"action-{index}-" + "x" * 600 for index in range(12)],
        open_questions=[f"question-{index}-" + "x" * 600 for index in range(12)],
        constraints=[f"constraint-{index}-" + "x" * 600 for index in range(12)],
    )

    asyncio.run(SessionContinuityManagerService(store).update(context))

    memory = store.saved_memory
    assert memory is not None
    assert len(memory.session_working_summary or "") <= 2000
    assert len(memory.latest_action_items) == 10
    assert len(memory.open_questions) == 10
    assert all(len(item) <= 500 for item in memory.latest_action_items)
    assert all(len(item) <= 500 for item in memory.open_questions)
    assert len(memory.temporary_context["constraints"]) == 10
    assert all(len(item) <= 500 for item in memory.temporary_context["constraints"])


def test_load_failure_does_not_save_or_raise() -> None:
    store = _RecordingSessionStore(load_error=RuntimeError("load failed"))

    asyncio.run(SessionContinuityManagerService(store).update(_context()))

    assert store.saved_memory is None
    assert len(store.load_calls) == 1


def test_save_failure_does_not_raise() -> None:
    store = _RecordingSessionStore(save_error=RuntimeError("save failed"))

    asyncio.run(SessionContinuityManagerService(store).update(_context()))

    assert store.saved_memory is None


def test_missing_session_boundary_skips_store_access() -> None:
    store = _RecordingSessionStore()
    context = ExecutionContext.model_construct(
        running_state=RunningState(original_query="A question."),
        runtime_context=RuntimeContext.model_construct(
            request_id="run-1",
            user_id="user-1",
            session_id="",
        ),
    )

    asyncio.run(SessionContinuityManagerService(store).update(context))

    assert store.load_calls == []
    assert store.saved_memory is None
