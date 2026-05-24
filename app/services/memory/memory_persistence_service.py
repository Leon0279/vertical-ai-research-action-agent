"""Memory persistence skeleton."""

from __future__ import annotations

from uuid import uuid4

from app.adapters.memory.contracts.long_term_memory_store_protocol import LongTermMemoryStoreProtocol
from app.domain.models import ExecutionState, MemoryRecord


class MemoryPersistenceService:
    """Persist memory candidates into long-term store."""

    def __init__(self, long_term_store: LongTermMemoryStoreProtocol) -> None:
        self._long_term_store = long_term_store

    async def persist(self, state: ExecutionState) -> None:
        records = [
            MemoryRecord(
                record_id=f"mem-{uuid4().hex}",
                memory_type=candidate.memory_type,
                payload=candidate.payload | {"summary": candidate.summary},
            )
            for candidate in state.memory_candidates
        ]
        if records:
            await self._long_term_store.upsert(records)
