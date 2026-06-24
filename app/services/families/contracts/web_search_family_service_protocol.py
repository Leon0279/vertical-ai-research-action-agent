"""Contract for the web_search family service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import WebSearchFamilyRequest, WebSearchFamilyResult


@runtime_checkable
class WebSearchFamilyServiceProtocol(Protocol):
    """Runtime-facing interface for the web_search family service."""

    async def run(self, request: WebSearchFamilyRequest) -> WebSearchFamilyResult:
        """Select a web_search tool, execute it, and return a family-level result."""
