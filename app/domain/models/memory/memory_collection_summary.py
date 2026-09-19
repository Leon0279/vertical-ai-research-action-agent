"""Aggregate statistics for one Memory collection."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MemoryCollectionSummary(BaseModel):
    """Represent a filtered Memory collection count and latest update time."""

    model_config = ConfigDict(extra="forbid")

    count: int = Field(ge=0)
    last_updated_at: datetime | None = None
