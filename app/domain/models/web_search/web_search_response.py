"""Response model for normalized web search results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.web_search.web_search_result import WebSearchResult


class WebSearchResponse(BaseModel):
    """Normalized web search response."""

    results: list[WebSearchResult] = Field(
        default_factory=list,
        description="Normalized web search results.",
    )
    source_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of searched provider metadata and result counts.",
    )
