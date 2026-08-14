"""Contract for provider-backed docs search clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import DocsSearchQuery, DocsSearchResponse


@runtime_checkable
class DocsSearchClientProtocol(Protocol):
    """定义文档搜索客户端的抽象交互契约。

Provider-neutral interface for docs-oriented retrieval adapters."""

    async def search_docs(self, query: DocsSearchQuery) -> DocsSearchResponse:
        """Search documentation sources for normalized docs fragments."""
