"""Contract for research knowledge memory stores."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.domain.models import (
    ResearchKnowledgeRecallQuery,
    ResearchKnowledgeRecallResult,
    ResearchKnowledgeUnitRecord,
    MemoryCollectionSummary,
)
from app.domain.models.memory.research_knowledge_visibility_scope import (
    ResearchKnowledgeVisibilityScope,
)


@runtime_checkable
class ResearchKnowledgeMemoryStoreProtocol(Protocol):
    """定义研究知识记忆存储的抽象交互契约。

Protocol for the research_knowledge_units adapter."""

    async def get_knowledge_unit(
        self,
        *,
        owner_user_id: str,
        knowledge_id: str,
    ) -> ResearchKnowledgeUnitRecord | None:
        """按用户边界和 knowledge id 读取单条研究知识单元。

        Args:
            owner_user_id (str): 知识单元所属用户标识，用于隔离访问范围。
            knowledge_id (str): 需要读取的 research knowledge unit 标识。

        Returns:
            ResearchKnowledgeUnitRecord | None: 对应知识单元；不存在或不属于该用户时返回 None。
        """

    async def upsert_knowledge_unit(self, unit: ResearchKnowledgeUnitRecord) -> None:
        """新增或更新一条 typed research knowledge unit。

        Args:
            unit (ResearchKnowledgeUnitRecord): 需要持久化的完整知识单元，包含摘要、范围、provenance、去重与生命周期信息。

        Returns:
            None: 写入成功后无返回值；底层存储异常由实现向调用方抛出。
        """

    async def find_active_by_dedupe_key(
        self,
        *,
        owner_user_id: str,
        dedupe_key: str,
    ) -> ResearchKnowledgeUnitRecord | None:
        """按用户边界和 dedupe key 查找当前有效的 canonical 知识单元。

        Args:
            owner_user_id (str): 知识单元所属用户标识，用于隔离查询范围。
            dedupe_key (str): 用于识别近似重复知识的归一化 key。

        Returns:
            ResearchKnowledgeUnitRecord | None: 匹配的 active canonical 知识单元；未找到时返回 None。
        """

    async def recall_knowledge_units(
        self,
        query: ResearchKnowledgeRecallQuery,
    ) -> list[ResearchKnowledgeRecallResult]:
        """使用 metadata 过滤和 pgvector 相似度召回有限数量的研究知识单元。

        Args:
            query (ResearchKnowledgeRecallQuery): 已包含 query embedding、范围和过滤条件的 recall 查询对象。

        Returns:
            list[ResearchKnowledgeRecallResult]: 按相关性返回的知识单元及其 adapter-level relevance score 列表。
        """

    async def list_knowledge_units_page(
        self,
        *,
        owner_user_id: str,
        project_scope_id: str,
        visibility_scopes: list[ResearchKnowledgeVisibilityScope],
        limit: int,
        after_updated_at: datetime | None = None,
        after_knowledge_id: str | None = None,
    ) -> list[ResearchKnowledgeUnitRecord]:
        """分页浏览当前用户和项目上下文中可见的有效知识单元。"""

    async def summarize_knowledge_units(
        self,
        *,
        owner_user_id: str,
        project_scope_id: str,
        visibility_scopes: list[ResearchKnowledgeVisibilityScope],
    ) -> MemoryCollectionSummary:
        """Aggregate active canonical unmerged knowledge for the requested scopes."""
