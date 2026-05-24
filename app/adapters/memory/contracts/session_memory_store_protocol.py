"""Contract for session memory stores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import SessionMemory


@runtime_checkable
class SessionMemoryStoreProtocol(Protocol):
    """Protocol for short-term session memory storage."""

    async def load(self, session_id: str | None) -> SessionMemory | None:
        """Load session memory by session id."""

    async def save(self, memory: SessionMemory) -> None:
        """Persist session memory."""
