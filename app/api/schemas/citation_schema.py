"""API schema for citations."""

from pydantic import BaseModel, Field


class CitationSchema(BaseModel):
    """User-facing citation structure."""

    source: str = Field(..., description="Citation source identifier.")
    note: str | None = Field(default=None, description="Optional citation note.")

