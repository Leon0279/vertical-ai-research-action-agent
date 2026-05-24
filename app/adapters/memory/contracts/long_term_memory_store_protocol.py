"""Contract for long-term memory stores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import MemoryRecord


@runtime_checkable
class LongTermMemoryStoreProtocol(Protocol):
    """Protocol for durable memory storage."""

    async def query(self, text: str, limit: int = 10) -> list[MemoryRecord]:
        """Query durable memory records by text relevance."""

    async def upsert(self, records: list[MemoryRecord]) -> None:
        """Persist durable memory records."""
