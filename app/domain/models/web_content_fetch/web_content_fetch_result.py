"""Domain models for normalized web content fetch results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

WebContentFetchStatus = Literal["succeeded", "empty_content"]


class WebContentFetchResult(BaseModel):
    """Normalized successful or degraded content extraction result."""

    item_id: str = Field(
        min_length=1,
        description="Stable result identifier for the fetched URL.",
    )
    url: str = Field(
        min_length=1,
        description="Original URL used as the fetch source.",
    )
    extracted_content: str | None = Field(
        default=None,
        description="Normalized extracted content when available.",
    )
    fetch_status: WebContentFetchStatus = Field(
        description="Status of the extraction result for this URL.",
    )
    images: list[str] = Field(
        default_factory=list,
        description="Optional extracted image URLs from the provider.",
    )
    favicon: str | None = Field(
        default=None,
        description="Optional source favicon URL from the provider.",
    )
    error_info: str | None = Field(
        default=None,
        description="Short adapter-level explanation for degraded successful results.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Lightweight provider metadata useful for provenance.",
    )
    source: str = Field(
        default="tavily_extract",
        description="Content fetch provider name for provenance.",
    )


class WebContentFetchFailedResult(BaseModel):
    """Normalized failed extraction result returned by the provider."""

    url: str = Field(
        min_length=1,
        description="Original URL that failed to be extracted.",
    )
    error_info: str = Field(
        min_length=1,
        description="Short provider or adapter-level failure explanation.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional provider failure metadata useful for debugging or provenance.",
    )
