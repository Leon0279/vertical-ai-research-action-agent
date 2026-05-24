"""Domain model for memory write-back candidates."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums.memory_type import MemoryType


class MemoryCandidate(BaseModel):
    """Potential long-term memory write-back item."""

    memory_type: MemoryType
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None

