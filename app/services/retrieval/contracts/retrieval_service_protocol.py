"""Contract for retrieval services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import EvidenceItem


@runtime_checkable
class RetrievalServiceProtocol(Protocol):
    """Retrieves evidence records."""

    async def retrieve(self, query: str, limit: int = 5) -> list[EvidenceItem]:
        """Retrieve evidence records."""
