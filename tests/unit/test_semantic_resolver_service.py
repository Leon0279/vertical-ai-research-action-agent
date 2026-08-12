"""Tests for the semantic resolver service skeleton."""

import asyncio

from app.domain.enums.memory_type import MemoryType
from app.domain.models import MemoryCandidate, MemoryRecord
from app.services.memory.semantic_resolver_service import SemanticResolverService


def test_semantic_resolver_is_a_noop_for_now() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="保留离线评测集方案。",
    )
    record = MemoryRecord(
        record_id="memory-1",
        memory_type=MemoryType.DECISION,
        payload={"summary": "已有方案。"},
    )

    result = asyncio.run(SemanticResolverService().resolve(candidate, [record]))

    assert result is None
    assert candidate.summary == "保留离线评测集方案。"
    assert record.payload == {"summary": "已有方案。"}
