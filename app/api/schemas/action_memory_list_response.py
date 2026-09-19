"""Paginated Action Memory list response schema."""

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.action_memory_item_response import ActionMemoryItemResponse


class ActionMemoryListResponse(BaseModel):
    """返回一个项目范围内按业务状态过滤的一页 Action Memory。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    items: list[ActionMemoryItemResponse] = Field(default_factory=list)
    next_cursor: str | None = None
