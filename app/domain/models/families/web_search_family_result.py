"""Domain model for web_search family results."""

from __future__ import annotations

from pydantic import Field

from app.domain.models.families.base_family_execution_result import BaseFamilyExecutionResult


class WebSearchFamilyResult(BaseFamilyExecutionResult):
    """Normalized family-level output returned by the web_search family service."""
    selected_family: str = Field(
        default="web_search",
        description="Family selected by the upstream execution layer.",
    )
