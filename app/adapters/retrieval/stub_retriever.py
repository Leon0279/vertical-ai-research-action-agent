"""In-memory retrieval stub."""

from app.domain.models import EvidenceItem


class StubRetriever:
    """Stub retriever that returns no records by default."""

    async def retrieve(self, query: str, limit: int = 5) -> list[EvidenceItem]:
        _ = (query, limit)
        return []
