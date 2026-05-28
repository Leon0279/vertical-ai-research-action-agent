"""In-memory session store for phase-1 skeleton."""

from __future__ import annotations

from app.adapters.memory.contracts.session_memory_store_protocol import SessionMemoryStoreProtocol
from app.domain.models import SessionMemory


class InMemorySessionStore(SessionMemoryStoreProtocol):
    """Simple in-process store for session memory."""

    def __init__(self) -> None:
        self._store: dict[str, SessionMemory] = {}

    async def load(self, session_id: str | None) -> SessionMemory | None:
        if not session_id:
            return None
        return self._store.get(session_id)

    async def save(self, memory: SessionMemory) -> None:
        if memory.session_id:
            self._store[memory.session_id] = memory
