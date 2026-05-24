"""Domain model for conclusion results."""

from pydantic import BaseModel, Field

from app.domain.models.action_item import ActionItem
from app.domain.models.citation import Citation
from app.domain.models.conclusion.final_recommendation import FinalRecommendation


class ConclusionResult(BaseModel):
    """Aggregated structured conclusion."""

    summary: str
    recommendation: FinalRecommendation | None = None
    action_items: list[ActionItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float | None = None
