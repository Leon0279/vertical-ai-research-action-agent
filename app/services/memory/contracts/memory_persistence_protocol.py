"""Contract for memory persistence services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import MemoryCandidate


@runtime_checkable
class MemoryPersistenceProtocol(Protocol):
    """Persists long-term memory candidates."""

    async def persist(self, candidates: list[MemoryCandidate]) -> None:
        """Persist memory candidates to a long-term store."""
