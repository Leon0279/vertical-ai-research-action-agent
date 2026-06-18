"""Contract for provider-backed web content fetch clients."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import WebContentFetchRequest, WebContentFetchResponse


@runtime_checkable
class WebContentFetchClientProtocol(Protocol):
    """Provider-neutral interface for normalized web content fetch adapters."""

    async def fetch_content(
        self,
        request: WebContentFetchRequest,
    ) -> WebContentFetchResponse:
        """Fetch and normalize extracted content for one or more URLs."""
