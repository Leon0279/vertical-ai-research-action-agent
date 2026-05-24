"""Domain model for long-term memory records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums.memory_type import MemoryType


class MemoryRecord(BaseModel):
    """Durable long-term memory record."""

    record_id: str
    memory_type: MemoryType
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

