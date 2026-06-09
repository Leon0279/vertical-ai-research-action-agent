"""Domain model for paper search queries."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaperSearchQuery(BaseModel):
    """Provider-neutral input for paper search."""

    query_text: str = Field(
        min_length=1,
        description="Free-text paper search query for the current request.",
    )
    limit: int = Field(
        default=5,
        description="Maximum number of paper results to return for this page.",
    )
    start: int = Field(
        default=0,
        description="Zero-based start offset for paginated paper search requests.",
    )
