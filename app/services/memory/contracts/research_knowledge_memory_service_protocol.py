"""Contract for Research Knowledge Memory application capabilities."""

from typing import Protocol, runtime_checkable

from app.domain.models.memory.research_knowledge_memory_page import (
    ResearchKnowledgeMemoryPage,
)
from app.domain.models.memory.memory_collection_summary import MemoryCollectionSummary
from app.domain.models.memory.research_knowledge_visibility_scope import (
    ResearchKnowledgeVisibilityScope,
)


@runtime_checkable
class ResearchKnowledgeMemoryServiceProtocol(Protocol):
    """定义 Research Knowledge Memory 浏览及后续领域能力的扩展边界。"""

    async def list_knowledge_units(
        self,
        *,
        user_id: str,
        project_id: str,
        visibility_scopes: list[ResearchKnowledgeVisibilityScope] | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ResearchKnowledgeMemoryPage:
        """按可见性范围读取一页 active canonical Research Knowledge。"""
        ...

    async def summarize_knowledge_units(
        self,
        *,
        user_id: str,
        project_id: str,
        visibility_scopes: list[ResearchKnowledgeVisibilityScope] | None = None,
    ) -> MemoryCollectionSummary:
        """按列表接口的可见性规则统计 Research Knowledge。"""
        ...
