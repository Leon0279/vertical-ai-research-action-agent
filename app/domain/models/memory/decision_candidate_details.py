"""Typed details proposed for decision memory."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DecisionCandidateDetails(BaseModel):
    """LLM-supported business fields for a decision candidate."""

    model_config = ConfigDict(extra="forbid")

    decision_title: str | None = None
    decision_question: str | None = None
    chosen_option: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    rationale: str | None = None
    tradeoffs: list[str] = Field(default_factory=list)
    decision_state: Literal[
        "proposed",
        "accepted",
        "reconsidering",
        "rejected",
    ] | None = None
    impact_scope: str | None = None
