"""Domain model for single evidence items."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """Single evidence record collected by retrieval or tools."""

    evidence_id: str
    source_type: str
    source_ref: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

