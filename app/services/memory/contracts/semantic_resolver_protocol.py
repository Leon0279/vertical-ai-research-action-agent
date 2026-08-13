"""Semantic resolution contract for memory persistence."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    ActionMemoryRecord,
    DecisionMemoryRecord,
    MemoryCandidate,
    PreferencePolicyMemoryRecord,
    ProjectProfileMemoryRecord,
    ResearchKnowledgeUnitRecord,
    SemanticResolutionResult,
)


StructuredMemoryRecord = (
    ProjectProfileMemoryRecord
    | DecisionMemoryRecord
    | ActionMemoryRecord
    | PreferencePolicyMemoryRecord
    | ResearchKnowledgeUnitRecord
)


@runtime_checkable
class SemanticResolverProtocol(Protocol):
    """为 memory persistence 提供重复、冲突和关系解析的扩展边界。"""

    async def resolve(
        self,
        candidate: MemoryCandidate,
        existing_records: list[StructuredMemoryRecord],
    ) -> SemanticResolutionResult:
        """解析 candidate 与已有记录的语义关系。"""
        ...
