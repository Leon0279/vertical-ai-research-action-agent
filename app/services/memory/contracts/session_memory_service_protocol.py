"""Contract for Session Memory application capabilities."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import SessionMemory


@runtime_checkable
class SessionMemoryServiceProtocol(Protocol):
    """Define the user/session-scoped Session Memory query boundary."""

    async def get_session(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> SessionMemory:
        """Load one current, non-expired compact Session Memory."""
        ...
