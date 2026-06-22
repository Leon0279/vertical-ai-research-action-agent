"""Domain model for arxiv_paper_search tool requests."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ArxivPaperSearchToolRequest(BaseModel):
    """Runtime-facing input for the arxiv_paper_search tool."""

    query_text: str = Field(
        min_length=1,
        description="Search query for the paper tool to execute.",
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description="Maximum number of paper search results to retain for tool output assembly.",
    )
    max_content_fetches: int = Field(
        default=3,
        ge=0,
        description="Maximum number of candidate papers to send to paper_content_fetch.",
    )
