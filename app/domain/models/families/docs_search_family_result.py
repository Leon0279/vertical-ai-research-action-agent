"""Domain model for docs_search family results."""

from __future__ import annotations

from pydantic import Field

from app.domain.models.families.base_family_execution_result import BaseFamilyExecutionResult


class DocsSearchFamilyResult(BaseFamilyExecutionResult):
    """Normalized family-level output returned by the docs_search family service."""
    selected_family: str = Field(
        default="docs_search",
        description="Family selected by the upstream execution layer.",
    )
