"""Domain model for retrieval query generation requests."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models.tool_execution_layer.evidence_shape import EvidenceShape

RetrievalFamily = Literal[
    "research_knowledge_recall",
    "docs_search",
    "paper_search",
    "web_search",
]


class RetrievalQueryGenerationRequest(BaseModel):
    """Input for generating an initial query for a selected retrieval family."""

    selected_family: RetrievalFamily = Field(
        description="Family already selected by family selection; this service does not choose tools.",
    )
    target_problem: str = Field(
        description="Current retrieval target problem or evidence need.",
    )
    evidence_goal: str | None = Field(
        default=None,
        description="Optional evidence acquisition goal, such as establish_coverage.",
    )
    evidence_shape: EvidenceShape | None = Field(
        default=None,
        description="Optional evidence shape hints used to tune query wording.",
    )
    success_hint: str | None = Field(
        default=None,
        description="Optional hint describing what useful retrieval results should look like.",
    )
    task_framing: str | None = Field(
        default=None,
        description="Optional upstream task framing used only as low-priority context.",
    )
    recent_low_value_queries: list[str] = Field(
        default_factory=list,
        description="Recent low-value query phrasings to avoid for this family/problem.",
    )
