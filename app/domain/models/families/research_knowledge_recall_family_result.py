"""Domain model for research_knowledge_recall family results."""

from __future__ import annotations

from pydantic import Field

from app.domain.models.families.base_family_execution_result import BaseFamilyExecutionResult


class ResearchKnowledgeRecallFamilyResult(BaseFamilyExecutionResult):
    """Normalized family-level output returned by the research_knowledge_recall family service."""
    selected_family: str = Field(
        default="research_knowledge_recall",
        description="Family selected by the upstream execution layer.",
    )
