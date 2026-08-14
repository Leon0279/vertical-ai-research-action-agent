"""Memory service migration tests for ExecutionContext."""

import asyncio

from app.adapters.memory.in_memory_session_store import InMemorySessionStore
from app.domain.models import ExecutionContext, RunningState, RuntimeContext, SessionMemory
from app.services.memory.session_continuity_manager_service import SessionContinuityManagerService


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
    assert memory.session_working_summary is not None
    assert "Compare retrieval approaches." in memory.session_working_summary
    assert memory.latest_action_items == ["Run a small evaluation."]
    assert memory.temporary_context["project_scope_id"] == "project-1"
