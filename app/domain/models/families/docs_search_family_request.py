"""Domain model for docs_search family requests."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocsSearchFamilyRequest(BaseModel):
    """Runtime-facing input for the docs_search family service."""

    query_text: str = Field(
        min_length=1,
        description="Search query for the docs_search family to execute.",
    )
    target_problem: str | None = Field(
        default=None,
        description="Optional higher-level acquisition intent for the docs query.",
    )
    freshness_requirement: str | None = Field(
        default=None,
        description="Optional freshness hint forwarded to docs search.",
    )
    sub_source_types: list[str] = Field(
        default_factory=list,
        description="Optional configured docs sub-source types to restrict the family execution to.",
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description="Maximum number of docs search results to retain for family execution.",
    )
    preferred_tool: str | None = Field(
        default=None,
        description="Optional preferred tool identifier within the docs_search family.",
    )
