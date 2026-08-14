"""Contract for provider-backed web search clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import WebSearchQuery, WebSearchResponse


@runtime_checkable
class WebSearchClientProtocol(Protocol):
    """定义网页搜索客户端的抽象交互契约。

Provider-neutral interface for normalized web search adapters."""

    async def search_web(self, query: WebSearchQuery) -> WebSearchResponse:
        """执行网页搜索并返回归一化结果条目。

        Args:
            query (WebSearchQuery): 网页检索查询，包含查询文本、结果数量与 provider 相关选项。

        Returns:
            WebSearchResponse: adapter 归一化后的网页搜索响应，包含结果、丢弃统计和来源摘要。
        """
