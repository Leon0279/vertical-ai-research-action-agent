"""Contract for provider-backed docs search clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import DocsSearchQuery, DocsSearchResponse


@runtime_checkable
class DocsSearchClientProtocol(Protocol):
    """定义文档搜索客户端的抽象交互契约。

Provider-neutral interface for docs-oriented retrieval adapters."""

    async def search_docs(self, query: DocsSearchQuery) -> DocsSearchResponse:
        """在配置的文档来源中检索并返回归一化结果。

        Args:
            query (DocsSearchQuery): 文档检索查询，包含查询文本、结果数量及可选来源过滤条件。

        Returns:
            DocsSearchResponse: adapter 归一化后的文档检索响应，包含结果、丢弃统计和来源摘要。
        """
