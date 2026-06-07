"""Canonical mutable state for a single request run."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums.planning_depth import PlanningDepth
from app.domain.enums.workflow_pattern import WorkflowPattern
from app.domain.models.workflow_execution_policy import WorkflowExecutionPolicy


class RunningState(BaseModel):
    """Canonical mutable state for a single request run."""

    original_query: str = Field(
        min_length=1,
        description="The user's original query for the current run.",
    )
    task_type: str | None = Field(
        default=None,
        description=(
            "The top-level task category for the current run, such as "
            "topic_exploration, comparison, recommendation, or action_planning."
        ),
    )
    user_goal: str | None = Field(
        default=None,
        description="The underlying objective the current request is trying to achieve.",
    )
    task_framing: str | None = Field(
        default=None,
        description=(
            "A high-level framing for how the current problem should be handled, "
            "such as project_specific_recommendation or engineering_tradeoff_comparison."
        ),
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Explicit constraints currently in force for this run.",
    )

    project_scope_id: str | None = Field(
        default=None,
        description="The resolved project scope identifier for the current run, if any.",
    )
    project_context_summary: str | None = Field(
        default=None,
        description="A distilled summary of the current project's background and context.",
    )
    current_bottleneck_summary: str | None = Field(
        default=None,
        description="A distilled summary of the most important current bottleneck.",
    )
    active_decision_summary: str | None = Field(
        default=None,
        description="A summary of the active decisions that still materially affect this run.",
    )
    current_action_status: str | None = Field(
        default=None,
        description="A distilled summary of the current project action and execution status.",
    )

    workflow_pattern: WorkflowPattern | None = Field(
        default=None,
        description="Workflow pattern selected by the Workflow Router for downstream stages.",
    )
    execution_policy: WorkflowExecutionPolicy | None = Field(
        default=None,
        description="Lightweight execution policy selected by the Workflow Router.",
    )

    planning_depth: PlanningDepth = Field(
        default=PlanningDepth.NONE,
        description="Selected planning depth for the current run.",
    )
    plan: list[str] = Field(
        default_factory=list,
        description="The current execution plan for this run.",
    )
    sub_questions: list[str] = Field(
        default_factory=list,
        description="The sub-questions derived for the current run.",
    )
    comparison_candidates: list[str] = Field(
        default_factory=list,
        description="The candidate options being compared in the current run.",
    )
    information_gaps: list[str] = Field(
        default_factory=list,
        description="Known information gaps that have not yet been filled.",
    )
    initial_evidence_strategy: list[str] = Field(
        default_factory=list,
        description="Initial evidence-gathering guidance produced by planning.",
    )

    retrieved_evidence_refs: list[str] = Field(
        default_factory=list,
        description="References to evidence already accepted in the current run.",
    )
    evidence_summary: str | None = Field(
        default=None,
        description="A summary of the evidence layer accumulated so far.",
    )
    intermediate_findings: list[str] = Field(
        default_factory=list,
        description="Intermediate findings or provisional judgments formed during the run.",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Questions that remain unresolved in the current run.",
    )

    final_recommendation: str | None = Field(
        default=None,
        description="The final recommendation once the run has converged.",
    )
    action_items: list[str] = Field(
        default_factory=list,
        description="The concrete action items produced by the current run.",
    )
    confidence: str | None = Field(
        default=None,
        description="The overall confidence level for the current run, such as low, medium, or high.",
    )
