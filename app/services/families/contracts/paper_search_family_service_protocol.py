"""Contract for the paper_search family service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import PaperSearchFamilyRequest, PaperSearchFamilyResult


@runtime_checkable
class PaperSearchFamilyServiceProtocol(Protocol):
    """Runtime-facing interface for the paper_search family service."""

    async def run(self, request: PaperSearchFamilyRequest) -> PaperSearchFamilyResult:
        """Select a paper_search tool, execute it, and return a family-level result."""
