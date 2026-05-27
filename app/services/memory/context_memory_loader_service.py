"""Context and memory loading skeleton."""

from __future__ import annotations

from app.adapters.memory.contracts.long_term_memory_store_protocol import LongTermMemoryStoreProtocol
from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.domain.models import ExecutionState
from app.services.memory.contracts.context_memory_loader_protocol import ContextMemoryLoaderProtocol


class ContextMemoryLoaderService(ContextMemoryLoaderProtocol):
    """Load task-relevant short-term and long-term memory."""

    def __init__(
        self,
        session_store: SessionMemoryStoreProtocol,
        long_term_store: LongTermMemoryStoreProtocol,
    ) -> None:
        self._session_store = session_store
        self._long_term_store = long_term_store

    async def load(self, state: ExecutionState) -> None:
        session_memory = await self._session_store.load(session_id=state.project_context.get("session_id"))
        long_term_records = await self._long_term_store.query(text=state.original_query, limit=5)

        state.session_memory = session_memory
        state.loaded_memory_records = long_term_records
