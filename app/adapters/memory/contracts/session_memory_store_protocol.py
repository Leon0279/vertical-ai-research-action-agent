"""Contract for session memory stores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import SessionMemory


@runtime_checkable
class SessionMemoryStoreProtocol(Protocol):
    """定义会话记忆存储的抽象交互契约。

Protocol for short-term session memory storage."""

    async def load(self, *, user_id: str, session_id: str | None) -> SessionMemory | None:
        """Load session memory by user and session boundary."""

    async def save(self, memory: SessionMemory) -> None:
        """Persist session memory."""
