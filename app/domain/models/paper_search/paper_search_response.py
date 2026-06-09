"""Paged response model for normalized paper search results."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models.paper_search.paper_search_result import PaperSearchResult


class PaperSearchResponse(BaseModel):
    """Normalized paged paper search response."""

    results: list[PaperSearchResult] = Field(
        default_factory=list,
        description="Normalized paper search results for the current page.",
    )
    total_results: int | None = Field(
        default=None,
        description="Provider-reported total number of matching results.",
    )
    start_index: int | None = Field(
        default=None,
        description="Provider-reported start index for the current page.",
    )
    items_per_page: int | None = Field(
        default=None,
        description="Provider-reported number of items returned per page.",
    )
