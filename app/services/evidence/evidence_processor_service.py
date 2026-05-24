"""Evidence processing skeleton."""

from app.domain.models import EvidenceItem, EvidenceSummary


class EvidenceProcessorService:
    """Evidence normalization and summarization placeholder."""

    async def normalize(self, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        # TODO: implement deduplication and quality filtering.
        return evidence

    async def summarize(self, evidence: list[EvidenceItem]) -> EvidenceSummary:
        return EvidenceSummary(
            summary="No external evidence processed in Phase 1 stub.",
            key_points=[f"evidence_count={len(evidence)}"],
        )
