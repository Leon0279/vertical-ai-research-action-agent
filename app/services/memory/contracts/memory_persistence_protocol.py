"""Contract for memory persistence services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ExecutionState


@runtime_checkable
class MemoryPersistenceProtocol(Protocol):
    """Persists long-term memory candidates."""

    async def persist(self, state: ExecutionState) -> None:
        """Persist state memory candidates to a long-term store."""
