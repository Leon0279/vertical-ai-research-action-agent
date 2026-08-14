"""Contract for provider-backed web search clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import WebSearchQuery, WebSearchResponse


@runtime_checkable
class WebSearchClientProtocol(Protocol):
    """定义网页搜索客户端的抽象交互契约。

Provider-neutral interface for normalized web search adapters."""

    async def search_web(self, query: WebSearchQuery) -> WebSearchResponse:
        """Search the web and return normalized result items."""
