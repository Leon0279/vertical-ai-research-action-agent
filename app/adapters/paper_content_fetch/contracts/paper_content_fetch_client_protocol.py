"""Contract for provider-backed paper content fetch clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import PaperContentFetchRequest, PaperContentFetchResult


@runtime_checkable
class PaperContentFetchClientProtocol(Protocol):
    """Provider-neutral interface for paper fulltext fetch adapters."""

    async def fetch_content(
        self,
        request: PaperContentFetchRequest,
    ) -> PaperContentFetchResult:
        """Fetch and extract paper content for the given request."""
