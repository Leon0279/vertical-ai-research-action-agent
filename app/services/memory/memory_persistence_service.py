"""Memory persistence skeleton."""

from __future__ import annotations

from uuid import uuid4

from app.adapters.memory.contracts.long_term_memory_store_protocol import LongTermMemoryStoreProtocol
from app.domain.models import MemoryCandidate, MemoryRecord
from app.services.memory.contracts.memory_persistence_protocol import MemoryPersistenceProtocol


class MemoryPersistenceService(MemoryPersistenceProtocol):
    """将 memory candidates 转换为 durable records 并写入长期 memory store。"""

    def __init__(self, long_term_store: LongTermMemoryStoreProtocol) -> None:
        self._long_term_store = long_term_store

    async def persist(self, candidates: list[MemoryCandidate]) -> None:
        records = [
            MemoryRecord(
                record_id=f"mem-{uuid4().hex}",
                memory_type=candidate.memory_type,
                payload=self._record_payload(candidate),
            )
            for candidate in candidates
        ]
        if records:
            await self._long_term_store.upsert(records)

    @staticmethod
    def _record_payload(candidate: MemoryCandidate) -> dict[str, object]:
        """Build JSON-safe payload while keeping canonical candidate metadata authoritative."""

        payload: dict[str, object] = dict(candidate.payload)
        payload.update(
            {
                "summary": candidate.summary,
                "project_scope_id": candidate.project_scope_id,
                "candidate_source": candidate.candidate_source,
                "semantic_type": candidate.semantic_type,
                "stability": candidate.stability,
                "confidence": candidate.confidence,
                "source_references": [
                    source_reference.model_dump(mode="json")
                    for source_reference in candidate.source_references
                ],
                "derived_from_run_id": candidate.derived_from_run_id,
                "derived_from_session_id": candidate.derived_from_session_id,
            }
        )
        return payload
