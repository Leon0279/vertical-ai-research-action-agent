"""Contract for the arxiv_paper_search tool service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import ArxivPaperSearchToolRequest, ArxivPaperSearchToolResult


@runtime_checkable
class ArxivPaperSearchToolProtocol(Protocol):
    """定义arXiv论文搜索工具的抽象交互契约。

Runtime-facing interface for the arxiv_paper_search tool."""

    async def run(self, request: ArxivPaperSearchToolRequest) -> ArxivPaperSearchToolResult:
        """Execute the tool using the given request and return normalized retrieval output."""
