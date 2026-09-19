"""Paginated Policy Memory list response schema."""

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.policy_memory_item_response import PolicyMemoryItemResponse


class PolicyMemoryListResponse(BaseModel):
    """返回一个项目上下文内的一页 active Policy Memory。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    items: list[PolicyMemoryItemResponse] = Field(default_factory=list)
    next_cursor: str | None = None
