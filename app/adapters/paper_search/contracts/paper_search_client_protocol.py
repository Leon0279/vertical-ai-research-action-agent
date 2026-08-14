"""Contract for provider-backed paper search clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import PaperSearchQuery, PaperSearchResponse


@runtime_checkable
class PaperSearchClientProtocol(Protocol):
    """定义论文搜索客户端的抽象交互契约。

Provider-neutral interface for paper search adapters."""

    async def search_papers(self, query: PaperSearchQuery) -> PaperSearchResponse:
        """使用 provider-backed 实现检索论文元数据。

        Args:
            query (PaperSearchQuery): 论文检索查询，包含查询文本、数量限制和可选过滤条件。

        Returns:
            PaperSearchResponse: 归一化论文搜索响应，包含结果、丢弃统计和 provider 摘要。
        """
