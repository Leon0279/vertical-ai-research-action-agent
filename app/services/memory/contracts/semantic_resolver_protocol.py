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
        """解析记忆候选与同范围已有记录之间的确定性语义关系。

        Args:
            candidate (MemoryCandidate): 需要判断重复、变化或冲突关系的待持久化记忆候选。
            existing_records (list[StructuredMemoryRecord]): 已查询出的同类型、同范围 typed 长期记忆记录列表。

        Returns:
            SemanticResolutionResult: 描述候选与唯一匹配记录之间的关系和规则判断原因；
                没有匹配对象时返回 no_match，最终持久化动作仍由 persistence service 决定。
        """
        ...
