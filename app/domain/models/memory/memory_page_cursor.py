"""Versioned cursor model for memory collection pagination."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryPageCursor(BaseModel):
    """表示客户端不可见语义下的稳定 Memory keyset 游标。"""

    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    collection: Literal["decisions"]
    updated_at: datetime
    record_id: str = Field(min_length=1)

    @field_validator("updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Reject ambiguous timestamps that cannot define a stable global order."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("updated_at must include a timezone")
        return value
