"""Contract for retrieval backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import EvidenceItem


@runtime_checkable
class RetrieverProtocol(Protocol):
    """Protocol for retrieval backends."""

    async def retrieve(self, query: str, limit: int = 5) -> list[EvidenceItem]:
        """Retrieve evidence for a query."""
