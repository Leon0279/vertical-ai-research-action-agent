"""Domain model for docs search results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.source import SourceReference


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
    source_reference: SourceReference = Field(
        description="Canonical source provenance for this docs search result.",
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        description="Adapter-local relevance score.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Lightweight adapter-local metadata for ranking and fetch diagnostics.",
    )
