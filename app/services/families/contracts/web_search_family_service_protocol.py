"""Contract for the web_search family service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import WebSearchFamilyRequest, WebSearchFamilyResult


@runtime_checkable
class WebSearchFamilyServiceProtocol(Protocol):
    """定义网页搜索检索族服务的抽象交互契约。

Runtime-facing interface for the web_search family service."""

    async def run(self, request: WebSearchFamilyRequest) -> WebSearchFamilyResult:
        """执行网页搜索检索族，并返回 family 层归一化结果。

        Args:
            request (WebSearchFamilyRequest): 网页检索族请求，包含目标问题、查询、内容抓取设置和执行限制。

        Returns:
            WebSearchFamilyResult: 选用工具后的网页检索结果、归一化条目、执行摘要、追踪信息与获取状态。
        """
