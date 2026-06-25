"""Domain model for paper_search family results."""

from __future__ import annotations

from pydantic import Field

from app.domain.models.families.base_family_execution_result import BaseFamilyExecutionResult


class PaperSearchFamilyResult(BaseFamilyExecutionResult):
    """Normalized family-level output returned by the paper_search family service."""
    selected_family: str = Field(
        default="paper_search",
        description="Family selected by the upstream execution layer.",
    )
