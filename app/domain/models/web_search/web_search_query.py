"""Domain model for web search queries."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WebSearchQuery(BaseModel):
    """Provider-neutral input for web search retrieval."""

    query_text: str = Field(
        min_length=1,
        description="Open web search query for the current request.",
    )
    target_problem: str | None = Field(
        default=None,
        description="Higher-level retrieval target problem motivating this query.",
    )
    limit: int = Field(
        default=5,
        description="Maximum number of search results to return.",
    )
    freshness_requirement: str | None = Field(
        default=None,
        description="Optional freshness hint such as latest or recent.",
    )
    include_domains: list[str] = Field(
        default_factory=list,
        description="Optional allow-list of domains to prefer or restrict the search to.",
    )
    exclude_domains: list[str] = Field(
        default_factory=list,
        description="Optional block-list of domains to exclude from search results.",
    )
