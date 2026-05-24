"""Domain model for evidence summaries."""

from pydantic import BaseModel, Field


class EvidenceSummary(BaseModel):
    """Structured summary of an evidence set."""

    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)

