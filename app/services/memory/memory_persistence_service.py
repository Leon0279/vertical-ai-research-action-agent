"""Memory persistence skeleton."""

from __future__ import annotations

from uuid import uuid4

from app.adapters.memory.contracts.long_term_memory_store_protocol import LongTermMemoryStoreProtocol
from app.domain.models import MemoryCandidate, MemoryRecord
from app.services.memory.contracts.memory_persistence_protocol import MemoryPersistenceProtocol
from app.services.memory.contracts.semantic_resolver_protocol import SemanticResolverProtocol


class MemoryPersistenceService(MemoryPersistenceProtocol):
    """将 memory candidates 转换为 durable records 并写入长期 memory store。"""

    def __init__(
        self,
        long_term_store: LongTermMemoryStoreProtocol,
        semantic_resolver: SemanticResolverProtocol,
    ) -> None:
        self._long_term_store = long_term_store
        self._semantic_resolver = semantic_resolver

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

    def _validate_candidates(self, candidates: list[MemoryCandidate]) -> None:
        """预留 candidate 最小持久化校验步骤。"""
        pass

    def _resolve_target_store(self, candidate: MemoryCandidate) -> None:
        """预留根据 memory type 解析目标 store 的步骤。"""
        pass

    async def _lookup_existing_records(self, candidate: MemoryCandidate) -> None:
        """预留查询同范围、同类型已有记录的步骤。"""
        pass

    def _decide_persistence_action(
        self,
        candidate: MemoryCandidate,
        existing_records: list[MemoryRecord],
    ) -> None:
        """预留 create、update、replace、supersede 或 no-write 决策步骤。"""
        pass

    def _shape_durable_record(
        self,
        candidate: MemoryCandidate,
        action: str,
        existing_records: list[MemoryRecord],
    ) -> None:
        """预留按目标 memory type 构造 durable record 的步骤。"""
        pass

    async def _execute_write(
        self,
        candidate: MemoryCandidate,
        record: MemoryRecord,
        action: str,
    ) -> None:
        """预留执行实际写入的步骤。"""
        pass

    def _build_post_write_result(
        self,
        candidate: MemoryCandidate,
        record: MemoryRecord | None,
        action: str,
    ) -> None:
        """预留构造结构化 post-write result 的步骤。"""
        pass

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
