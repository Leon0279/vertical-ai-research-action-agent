"""In-memory long-term store for phase-1 skeleton."""

from __future__ import annotations

from app.adapters.memory.contracts.long_term_memory_store_protocol import LongTermMemoryStoreProtocol
from app.domain.models import MemoryRecord


class InMemoryLongTermStore(LongTermMemoryStoreProtocol):
    """Simple in-process store for long-term memory records."""

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    async def query(self, text: str, limit: int = 10) -> list[MemoryRecord]:
        _ = text
        return self._records[:limit]

    async def upsert(self, records: list[MemoryRecord]) -> None:
        self._records.extend(records)
