"""In-memory session store for phase-1 skeleton."""

from __future__ import annotations

from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.domain.models import SessionMemory


class InMemorySessionStore(SessionMemoryStoreProtocol):
    """Simple in-process store for session memory."""

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], SessionMemory] = {}

    async def load(self, *, user_id: str, session_id: str | None) -> SessionMemory | None:
        if not user_id or not session_id:
            return None
        return self._store.get((user_id, session_id))

    async def save(self, memory: SessionMemory) -> None:
        if memory.user_id and memory.session_id:
            self._store[(memory.user_id, memory.session_id)] = memory
