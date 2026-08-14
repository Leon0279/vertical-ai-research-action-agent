"""Contract for the paper_search family service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import PaperSearchFamilyRequest, PaperSearchFamilyResult


@runtime_checkable
class PaperSearchFamilyServiceProtocol(Protocol):
    """定义论文搜索检索族服务的抽象交互契约。

Runtime-facing interface for the paper_search family service."""

    async def run(self, request: PaperSearchFamilyRequest) -> PaperSearchFamilyResult:
        """Select a paper_search tool, execute it, and return a family-level result."""
