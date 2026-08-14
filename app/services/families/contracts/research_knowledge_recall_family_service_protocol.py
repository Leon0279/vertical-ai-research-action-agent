"""Contract for the research_knowledge_recall family service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    ResearchKnowledgeRecallFamilyRequest,
    ResearchKnowledgeRecallFamilyResult,
)


@runtime_checkable
class ResearchKnowledgeRecallFamilyServiceProtocol(Protocol):
    """定义研究知识召回检索族服务的抽象交互契约。

Runtime-facing interface for the research_knowledge_recall family service."""

    async def run(
        self,
        request: ResearchKnowledgeRecallFamilyRequest,
    ) -> ResearchKnowledgeRecallFamilyResult:
        """Select a research_knowledge_recall tool, execute it, and return a family-level result."""
