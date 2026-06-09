"""Contract for provider-backed paper search clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import PaperSearchQuery, PaperSearchResponse


@runtime_checkable
class PaperSearchClientProtocol(Protocol):
    """Provider-neutral interface for paper search adapters."""

    async def search_papers(self, query: PaperSearchQuery) -> PaperSearchResponse:
        """Search for papers using a provider-backed query implementation."""
