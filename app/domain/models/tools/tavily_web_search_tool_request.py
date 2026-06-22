"""Domain model for tavily_web_search tool requests."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TavilyWebSearchToolRequest(BaseModel):
    """Runtime-facing input for the tavily_web_search tool."""

    query_text: str = Field(
        min_length=1,
        description="Search query for the tool to execute.",
    )
    target_problem: str | None = Field(
        default=None,
        description="Optional higher-level acquisition intent for the search query.",
    )
    freshness_requirement: str | None = Field(
        default=None,
        description="Optional freshness hint forwarded to web search.",
    )
    include_domains: list[str] = Field(
        default_factory=list,
        description="Optional domains to prioritize or restrict during search.",
    )
    exclude_domains: list[str] = Field(
        default_factory=list,
        description="Optional domains to exclude during search.",
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description="Maximum number of search results to retain for tool output assembly.",
    )
    max_content_fetches: int = Field(
        default=3,
        ge=0,
        description="Maximum number of candidate URLs to send to web_content_fetch.",
    )
    min_score_threshold: float = Field(
        default=0.5,
        ge=0.0,
        description="Minimum score threshold used when selecting content fetch candidates.",
    )
