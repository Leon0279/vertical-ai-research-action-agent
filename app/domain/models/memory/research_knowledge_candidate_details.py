"""Typed details proposed for research knowledge memory."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResearchKnowledgeCandidateDetails(BaseModel):
    """LLM-supported business fields for a research knowledge candidate."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    knowledge_type: str | None = None
    topic_tags: list[str] = Field(default_factory=list)
    freshness_sensitivity: Literal["low", "medium", "high"] | None = None
