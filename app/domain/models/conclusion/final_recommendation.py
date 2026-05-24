"""Domain model for final recommendations."""

from pydantic import BaseModel, Field


class FinalRecommendation(BaseModel):
    """Recommendation output."""

    recommendation: str
    rationale: str | None = None
    deferred_options: list[str] = Field(default_factory=list)

