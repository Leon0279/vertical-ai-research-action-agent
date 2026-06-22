"""Contract for the research_knowledge_memory tool service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    ResearchKnowledgeMemoryToolRequest,
    ResearchKnowledgeMemoryToolResult,
)


@runtime_checkable
class ResearchKnowledgeMemoryToolProtocol(Protocol):
    """Runtime-facing interface for the research_knowledge_memory tool."""

    async def run(
        self,
        request: ResearchKnowledgeMemoryToolRequest,
    ) -> ResearchKnowledgeMemoryToolResult:
        """Execute the tool using the given request and return normalized retrieval output."""
