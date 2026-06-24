"""Contract for the docs_search family service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import DocsSearchFamilyRequest, DocsSearchFamilyResult


@runtime_checkable
class DocsSearchFamilyServiceProtocol(Protocol):
    """Runtime-facing interface for the docs_search family service."""

    async def run(self, request: DocsSearchFamilyRequest) -> DocsSearchFamilyResult:
        """Select a docs_search tool, execute it, and return a family-level result."""
