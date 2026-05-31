"""Memory service migration tests for ExecutionContext."""

import asyncio

from app.adapters.memory.in_memory_long_term_store import InMemoryLongTermStore
from app.adapters.memory.in_memory_session_store import InMemorySessionStore
from app.domain.enums.memory_type import MemoryType
from app.domain.models import ExecutionContext, MemoryRecord, RunningState, RuntimeContext, SessionMemory
from app.services.memory.context_memory_loader_service import ContextMemoryLoaderService
from app.services.memory.session_continuity_manager_service import SessionContinuityManagerService


def test_context_memory_loader_populates_supplemental_context() -> None:
    session_store = InMemorySessionStore()
    long_term_store = InMemoryLongTermStore()

    async def run_test() -> ExecutionContext:
        await session_store.save(
            SessionMemory(
                user_id="user-1",
                session_id="session-1",
                session_working_summary="Compare retrieval approaches.",
                current_local_task_framing="Comparison of retrieval approaches.",
                latest_recommendation="Prefer the simpler baseline first.",
            )
        )
        await long_term_store.upsert(
            [
                MemoryRecord(
                    record_id="mem-1",
                    memory_type=MemoryType.DECISION,
                    payload={"summary": "Use Redis for session memory."},
                )
            ]
        )
        context = ExecutionContext(
            running_state=RunningState(original_query="Compare retrieval methods."),
            runtime_context=RuntimeContext(
                request_id="trace-1",
                user_id="user-1",
                session_id="session-1",
            ),
        )
        await ContextMemoryLoaderService(session_store, long_term_store).load(context)
        return context

    context = asyncio.run(run_test())

    assert len(context.supplemental_context.session_support) == 1
    assert context.supplemental_context.session_support[0].source_type == "session_memory"
    assert context.running_state.task_framing == "Comparison of retrieval approaches."
    assert len(context.supplemental_context.decision_support) == 1
    assert context.supplemental_context.decision_support[0].summary == "Use Redis for session memory."


def test_session_continuity_manager_uses_runtime_session_id() -> None:
    session_store = InMemorySessionStore()
    context = ExecutionContext(
        running_state=RunningState(
            original_query="Compare retrieval methods.",
            user_goal="Compare retrieval approaches.",
            task_type="COMPARISON",
            project_scope_id="project-1",
            final_recommendation="Prefer the simpler baseline first.",
            action_items=["Run a small evaluation."],
        ),
        runtime_context=RuntimeContext(
            request_id="trace-1",
            user_id="user-1",
            session_id="session-1",
        ),
    )

    async def run_test() -> SessionMemory | None:
        await SessionContinuityManagerService(session_store).update(context)
        return await session_store.load(user_id="user-1", session_id="session-1")

    memory = asyncio.run(run_test())

    assert memory is not None
    assert memory.user_id == "user-1"
    assert memory.session_id == "session-1"
    assert memory.session_working_summary == "Compare retrieval approaches."
    assert memory.latest_action_items == ["Run a small evaluation."]
    assert memory.temporary_context["project_scope_id"] == "project-1"
