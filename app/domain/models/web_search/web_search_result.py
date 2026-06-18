"""Domain model for normalized web search results."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WebSearchResult(BaseModel):
    """Normalized web search result returned by web search adapters."""

    item_id: str = Field(
        min_length=1,
        description="Stable result identifier within the web search response.",
    )
    title: str = Field(
        min_length=1,
        description="Result title shown by the search provider.",
    )
    snippet: str = Field(
        min_length=1,
        description="Result snippet returned by the search provider.",
    )
    url: str = Field(
        min_length=1,
        description="Original result URL.",
    )
    source_name: str = Field(
        min_length=1,
        description="Underlying search provider name.",
    )
    published_at: datetime | None = Field(
        default=None,
        description="Provider-reported publication time when available.",
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        description="Adapter-local relevance score from the provider response.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Lightweight provider metadata kept for provenance.",
    )
