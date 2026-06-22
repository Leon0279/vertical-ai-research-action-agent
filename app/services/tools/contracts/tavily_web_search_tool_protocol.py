"""Contract for the tavily_web_search tool service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import TavilyWebSearchToolRequest, TavilyWebSearchToolResult


@runtime_checkable
class TavilyWebSearchToolProtocol(Protocol):
    """Runtime-facing interface for the tavily_web_search tool."""

    async def run(self, request: TavilyWebSearchToolRequest) -> TavilyWebSearchToolResult:
        """Execute the tool using the given request and return normalized retrieval output."""
