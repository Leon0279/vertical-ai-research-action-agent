"""Retrieval service implementation using adapter protocol."""

from app.adapters.retrieval.contracts.retriever_protocol import RetrieverProtocol
from app.domain.models import EvidenceItem
from app.services.retrieval.contracts.retrieval_service_protocol import RetrievalServiceProtocol


class RetrievalService(RetrievalServiceProtocol):
    """Service wrapper over retrieval adapter."""

    def __init__(self, retriever: RetrieverProtocol) -> None:
        self._retriever = retriever

    async def retrieve(self, query: str, limit: int = 5) -> list[EvidenceItem]:
        return await self._retriever.retrieve(query=query, limit=limit)
