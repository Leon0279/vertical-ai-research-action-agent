"""Domain model for docs search queries."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocsSearchQuery(BaseModel):
    """Provider-neutral input for docs-oriented retrieval."""

    query_text: str = Field(
        min_length=1,
        description="Docs-oriented search query for the current request.",
    )
    target_problem: str | None = Field(
        default=None,
        description="Higher-level retrieval target problem that motivated this query.",
    )
    limit: int = Field(
        default=5,
        description="Maximum number of docs results to return.",
    )
    freshness_requirement: str | None = Field(
        default=None,
        description="Optional freshness hint from the acquisition intent.",
    )
    breadth: str | None = Field(
        default=None,
        description="Optional breadth hint such as narrow or broad.",
    )
    source_names: list[str] = Field(
        default_factory=list,
        description="Optional allow-list of configured docs source names.",
    )
