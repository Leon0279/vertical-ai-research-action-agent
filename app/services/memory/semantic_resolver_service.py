"""Semantic resolution service skeleton."""

from __future__ import annotations

from app.domain.models import MemoryCandidate, MemoryRecord
from app.services.memory.contracts.semantic_resolver_protocol import SemanticResolverProtocol


class SemanticResolverService(SemanticResolverProtocol):
    """Memory persistence 的语义解析扩展点。"""

    async def resolve(
        self,
        candidate: MemoryCandidate,
        existing_records: list[MemoryRecord],
    ) -> None:
        """预留重复、冲突及更新关系判断；本轮不执行任何处理。"""
        pass
