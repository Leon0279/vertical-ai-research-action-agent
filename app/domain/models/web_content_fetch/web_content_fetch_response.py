"""Response model for normalized web content fetch results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.web_content_fetch.web_content_fetch_result import (
    WebContentFetchFailedResult,
    WebContentFetchResult,
)


class WebContentFetchResponse(BaseModel):
    """Normalized web content fetch response."""

    results: list[WebContentFetchResult] = Field(
        default_factory=list,
        description="Normalized successful or degraded extraction results.",
    )
    failed_results: list[WebContentFetchFailedResult] = Field(
        default_factory=list,
        description="Normalized failed extraction results reported by the provider.",
    )
    response_time: float | None = Field(
        default=None,
        description="Provider-reported response time in seconds when available.",
    )
    request_id: str | None = Field(
        default=None,
        description="Provider-reported request identifier when available.",
    )
    usage: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional provider usage metadata.",
    )
    source_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of provider metadata and normalized result counts.",
    )
