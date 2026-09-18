"""Paginated Decision Memory list response schema."""

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.decision_memory_item_response import (
    DecisionMemoryItemResponse,
)


class DecisionMemoryListResponse(BaseModel):
    """返回一个项目范围内的一页 active Decision Memory。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    items: list[DecisionMemoryItemResponse] = Field(default_factory=list)
    next_cursor: str | None = None
