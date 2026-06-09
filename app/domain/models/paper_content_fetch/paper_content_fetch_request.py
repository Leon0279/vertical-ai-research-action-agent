"""Domain model for paper content fetch requests."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaperContentFetchRequest(BaseModel):
    """Provider-neutral input for fetching paper full text content."""

    arxiv_id: str | None = Field(
        default=None,
        description="arXiv identifier to resolve into a PDF URL.",
    )
    pdf_url: str | None = Field(
        default=None,
        description="Direct PDF URL to download and extract.",
    )
    paper_id: str | None = Field(
        default=None,
        description="Optional caller-provided stable paper identifier.",
    )
