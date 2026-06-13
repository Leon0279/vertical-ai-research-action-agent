"""Domain model for docs search results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocsSearchResult(BaseModel):
    """Normalized docs search result returned by docs adapters."""

    item_id: str = Field(
        min_length=1,
        description="Stable result identifier within the docs search response.",
    )
    title: str = Field(
        min_length=1,
        description="Documentation page or section title.",
    )
    content: str = Field(
        min_length=1,
        description="Documentation snippet or guidance text.",
    )
    source_name: str = Field(
        min_length=1,
        description="Configured docs source name.",
    )
    source_ref: str = Field(
        min_length=1,
        description="Original documentation reference, usually a URL.",
    )
    url: str | None = Field(
        default=None,
        description="Documentation URL when available.",
    )
    section: str | None = Field(
        default=None,
        description="Documentation section label when available.",
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        description="Adapter-local relevance score.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Lightweight source metadata for provenance.",
    )
