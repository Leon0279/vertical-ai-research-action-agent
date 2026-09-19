"""Contract for listing Research Knowledge Memories in a project context."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models.memory.research_knowledge_memory_page import (
    ResearchKnowledgeMemoryPage,
)
from app.domain.models.memory.research_knowledge_visibility_scope import (
    ResearchKnowledgeVisibilityScope,
)


@runtime_checkable
class ListResearchKnowledgeMemoriesUseCaseServiceProtocol(Protocol):
    """Coordinate project authorization and Research Knowledge browsing."""

    async def execute(
        self,
        *,
        user_id: str,
        project_id: str,
        visibility_scopes: list[ResearchKnowledgeVisibilityScope] | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ResearchKnowledgeMemoryPage:
        """Return one page after validating that the project belongs to the user."""
