"""Normalized paper search result model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PaperSearchResult(BaseModel):
    """Normalized paper metadata returned by external paper search adapters."""

    paper_id: str = Field(
        min_length=1,
        description="Stable internal paper result identifier for the current provider.",
    )
    title: str = Field(
        min_length=1,
        description="Paper title.",
    )
    authors: list[str] = Field(
        default_factory=list,
        description="Ordered author names listed for the paper.",
    )
    summary: str | None = Field(
        default=None,
        description="Paper summary or abstract text when available.",
    )
    published_at: datetime | None = Field(
        default=None,
        description="Original published timestamp when provided by the provider.",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Last updated timestamp when provided by the provider.",
    )
    arxiv_id: str = Field(
        min_length=1,
        description="Canonical arXiv identifier for the paper entry.",
    )
    primary_category: str | None = Field(
        default=None,
        description="Primary arXiv category for the paper when present.",
    )
    categories: list[str] = Field(
        default_factory=list,
        description="All arXiv category terms associated with the paper.",
    )
    url: str | None = Field(
        default=None,
        description="Abstract page URL for the paper.",
    )
    pdf_url: str | None = Field(
        default=None,
        description="Provider-reported PDF URL when available.",
    )
    doi_url: str | None = Field(
        default=None,
        description="DOI URL when a DOI is attached to the paper entry.",
    )
    source: str = Field(
        default="arxiv",
        description="Paper search provider name for provenance.",
    )
