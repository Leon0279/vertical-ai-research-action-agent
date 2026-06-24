"""Domain model for paper_search family requests."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaperSearchFamilyRequest(BaseModel):
    """Runtime-facing input for the paper_search family service."""

    query_text: str = Field(
        min_length=1,
        description="Search query for the paper_search family to execute.",
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description="Maximum number of paper search results to retain for family execution.",
    )
    max_content_fetches: int = Field(
        default=3,
        ge=0,
        description="Maximum number of candidate papers to send to paper content fetch.",
    )
    preferred_tool: str | None = Field(
        default=None,
        description="Optional preferred tool identifier within the paper_search family.",
    )
