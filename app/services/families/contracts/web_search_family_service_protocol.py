"""Contract for the web_search family service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import WebSearchFamilyRequest, WebSearchFamilyResult


@runtime_checkable
class WebSearchFamilyServiceProtocol(Protocol):
    """定义网页搜索检索族服务的抽象交互契约。

Runtime-facing interface for the web_search family service."""

    async def run(self, request: WebSearchFamilyRequest) -> WebSearchFamilyResult:
        """Select a web_search tool, execute it, and return a family-level result."""
