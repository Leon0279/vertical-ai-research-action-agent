"""Session continuity skeleton."""

from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.domain.models import ExecutionContext, SessionMemory
from app.services.memory.contracts.session_continuity_manager_protocol import (
    SessionContinuityManagerProtocol,
)


class SessionContinuityManagerService(SessionContinuityManagerProtocol):
    """Store task-relevant continuity fields in short-term memory."""

    def __init__(self, session_store: SessionMemoryStoreProtocol) -> None:
        self._session_store = session_store

    async def update(self, context: ExecutionContext) -> None:
        state = context.running_state
        session_id = context.runtime_context.session_id
        if not session_id:
            return

        memory = SessionMemory(
            session_id=session_id,
            active_user_goal=state.user_goal,
            active_task_type=state.task_type,
            task_framing=state.task_framing,
            latest_recommendation=state.final_recommendation,
            latest_action_items=state.action_items,
            session_project_context={"project_scope_id": state.project_scope_id},
            session_constraints={"constraints": state.constraints},
        )
        await self._session_store.save(memory)
