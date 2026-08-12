"""Semantic resolution contract for memory persistence."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import MemoryCandidate, MemoryRecord


@runtime_checkable
class SemanticResolverProtocol(Protocol):
    """为 memory persistence 提供重复、冲突和关系解析的扩展边界。"""

    async def resolve(
        self,
        candidate: MemoryCandidate,
        existing_records: list[MemoryRecord],
    ) -> None:
        """解析 candidate 与已有记录的语义关系；当前仅保留接口。"""
        ...
