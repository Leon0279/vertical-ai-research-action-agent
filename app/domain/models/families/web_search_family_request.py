"""Domain model for web_search family requests."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WebSearchFamilyRequest(BaseModel):
    """Runtime-facing input for the web_search family service."""

    query_text: str = Field(
        min_length=1,
        description="Search query for the web_search family to execute.",
    )
    target_problem: str | None = Field(
        default=None,
        description="Optional higher-level acquisition intent for the web search query.",
    )
    freshness_requirement: str | None = Field(
        default=None,
        description="Optional freshness hint forwarded to web search.",
    )
    include_domains: list[str] = Field(
        default_factory=list,
        description="Optional domains to prioritize or restrict during family execution.",
    )
    exclude_domains: list[str] = Field(
        default_factory=list,
        description="Optional domains to exclude during family execution.",
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description="Maximum number of web search results to retain for family execution.",
    )
    max_content_fetches: int = Field(
        default=3,
        ge=0,
        description="Maximum number of candidate URLs to send to web content fetch.",
    )
    min_score_threshold: float = Field(
        default=0.5,
        ge=0.0,
        description="Minimum score threshold used when selecting content fetch candidates.",
    )
    preferred_tool: str | None = Field(
        default=None,
        description="Optional preferred tool identifier within the web_search family.",
    )
