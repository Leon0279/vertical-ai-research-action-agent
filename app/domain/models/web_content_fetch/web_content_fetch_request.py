"""Domain model for web content fetch requests."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WebContentFetchRequest(BaseModel):
    """Provider-neutral input for extracting content from one or more URLs."""

    urls: list[str] = Field(
        default_factory=list,
        description="Absolute HTTP(S) URLs to extract content from.",
    )
    query: str | None = Field(
        default=None,
        description="Optional content extraction query to focus the returned chunks.",
    )
    chunks_per_source: int | None = Field(
        default=None,
        description="Optional number of chunks per source when query-based extraction is used.",
    )
    extract_depth: Literal["basic", "advanced"] | None = Field(
        default=None,
        description="Optional extraction depth override for the provider.",
    )
    include_images: bool | None = Field(
        default=None,
        description="Whether extracted image URLs should be included when supported.",
    )
    include_favicon: bool | None = Field(
        default=None,
        description="Whether source favicon URLs should be included when supported.",
    )
    format: Literal["markdown", "text"] | None = Field(
        default=None,
        description="Preferred extracted content format.",
    )
    timeout_seconds: float | None = Field(
        default=None,
        description="Optional provider-side extraction timeout in seconds.",
    )
    include_usage: bool | None = Field(
        default=None,
        description="Whether provider usage information should be requested.",
    )
