"""Session continuity skeleton."""

from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.domain.models import ExecutionState, SessionMemory
from app.services.memory.contracts.session_continuity_manager_protocol import (
    SessionContinuityManagerProtocol,
)


class SessionContinuityManagerService(SessionContinuityManagerProtocol):
    """Store task-relevant continuity fields in short-term memory."""

    def __init__(self, session_store: SessionMemoryStoreProtocol) -> None:
        self._session_store = session_store

    async def update(self, state: ExecutionState) -> None:
        session_id = state.project_context.get("session_id")
        if not session_id:
            return

        memory = SessionMemory(
            session_id=session_id,
            active_user_goal=state.user_goal,
            active_task_type=state.task_type.value if state.task_type else None,
            latest_recommendation=(
                state.final_recommendation.recommendation if state.final_recommendation else None
            ),
            latest_action_items=[item.title for item in state.action_items],
            session_project_context=state.project_context,
            session_constraints=state.constraints,
        )
        await self._session_store.save(memory)
