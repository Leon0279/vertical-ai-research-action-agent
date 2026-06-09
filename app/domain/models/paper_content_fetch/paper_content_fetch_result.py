"""Domain model for paper content fetch results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PaperContentExtractionStatus = Literal[
    "succeeded",
    "empty_text",
    "download_failed",
    "extraction_failed",
]


class PaperContentFetchResult(BaseModel):
    """Normalized paper fulltext fetch result returned by provider adapters."""

    paper_id: str = Field(
        min_length=1,
        description="Stable paper identifier for the fetched content.",
    )
    arxiv_id: str | None = Field(
        default=None,
        description="arXiv identifier when known.",
    )
    source_url: str = Field(
        min_length=1,
        description="PDF URL used as the source for this fetch result.",
    )
    extracted_text: str | None = Field(
        default=None,
        description="Extracted full text when extraction succeeds.",
    )
    extraction_status: PaperContentExtractionStatus = Field(
        description="Status of the download and text extraction attempt.",
    )
    error_info: str | None = Field(
        default=None,
        description="Short adapter-level failure explanation for degraded results.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific lightweight metadata useful for provenance.",
    )
    source: str = Field(
        default="arxiv",
        description="Content fetch provider name for provenance.",
    )
