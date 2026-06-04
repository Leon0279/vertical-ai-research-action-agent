"""Contract for research knowledge memory stores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    ResearchKnowledgeRecallQuery,
    ResearchKnowledgeRecallResult,
    ResearchKnowledgeUnitRecord,
)


@runtime_checkable
class ResearchKnowledgeMemoryStoreProtocol(Protocol):
    """Protocol for the research_knowledge_units adapter."""

    async def get_knowledge_unit(
        self,
        *,
        owner_user_id: str,
        knowledge_id: str,
    ) -> ResearchKnowledgeUnitRecord | None:
        """Load one knowledge unit by owner and id."""

    async def upsert_knowledge_unit(self, unit: ResearchKnowledgeUnitRecord) -> None:
        """Insert or update a research knowledge unit."""

    async def recall_knowledge_units(
        self,
        query: ResearchKnowledgeRecallQuery,
    ) -> list[ResearchKnowledgeRecallResult]:
        """Recall bounded knowledge units with metadata filters and pgvector similarity."""
