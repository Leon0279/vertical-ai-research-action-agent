"""Public response schema for one Memory collection summary."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryCollectionSummaryResponse(BaseModel):
    """公开单类长期 Memory 的数量和最近更新时间。"""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    count: int = Field(ge=0)
    last_updated_at: datetime | None = None
