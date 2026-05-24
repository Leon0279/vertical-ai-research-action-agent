"""Contract for evidence processing services."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import EvidenceItem, EvidenceSummary


@runtime_checkable
class EvidenceProcessorProtocol(Protocol):
    """Processes raw evidence into summary artifacts."""

    async def normalize(self, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        """Normalize and deduplicate evidence."""

    async def summarize(self, evidence: list[EvidenceItem]) -> EvidenceSummary:
        """Summarize evidence for downstream synthesis."""
