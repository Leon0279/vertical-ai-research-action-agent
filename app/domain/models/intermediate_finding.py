"""Intermediate finding models."""

from __future__ import annotations

from pydantic import BaseModel


class IntermediateFinding(BaseModel):
    """Working conclusion produced during execution loop."""

    statement: str
    rationale: str | None = None
    confidence: float | None = None

