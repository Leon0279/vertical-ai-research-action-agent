"""Workflow execution policy selected by the workflow router."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums.memory_type import MemoryType
from app.domain.enums.planning_depth import PlanningDepth


class WorkflowExecutionPolicy(BaseModel):
    """Lightweight downstream execution policy produced by workflow routing."""

    model_config = ConfigDict(extra="forbid")

    planning_depth: PlanningDepth = Field(
        description="Default planning depth that downstream planning should prefer.",
    )
    evidence_strategy: str = Field(
        min_length=1,
        description="High-level evidence strategy emphasis for research execution.",
    )
    output_emphasis: str = Field(
        min_length=1,
        description="High-level output structure emphasis for conclusion generation.",
    )
    memory_writeback_focus: list[MemoryType] = Field(
        default_factory=list,
        description="Long-term memory categories that downstream write-back should emphasize.",
    )
    comparison_needed: bool = Field(
        default=False,
        description="Whether downstream stages should emphasize structured comparison.",
    )
    recommendation_needed: bool = Field(
        default=False,
        description="Whether downstream stages should produce a decision-oriented recommendation.",
    )
    action_generation_needed: bool = Field(
        default=False,
        description="Whether downstream stages should produce next-step action outputs.",
    )
    tracking_needed: bool = Field(
        default=False,
        description="Whether downstream stages should emphasize update tracking.",
    )
    routing_confidence: str = Field(
        min_length=1,
        description="Router confidence label, such as high or low.",
    )
    fallback_reason: str | None = Field(
        default=None,
        description="Reason the router fell back to a conservative workflow, if any.",
    )
