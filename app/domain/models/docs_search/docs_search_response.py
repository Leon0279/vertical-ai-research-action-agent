"""Response model for normalized docs search results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.docs_search.docs_search_result import DocsSearchResult


class DocsSearchResponse(BaseModel):
    """Normalized docs search response."""

    results: list[DocsSearchResult] = Field(
        default_factory=list,
        description="Normalized docs search results.",
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description="Malformed manifest items dropped during normalization.",
    )
    source_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of searched sources and normalized result counts.",
    )
