"""Running execution state shared by orchestration stages."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums.planning_depth import PlanningDepth
from app.domain.enums.task_type import TaskType
from app.domain.enums.workflow_pattern import WorkflowPattern
from app.domain.models.action_item import ActionItem
from app.domain.models.conclusion.conclusion_result import ConclusionResult
from app.domain.models.conclusion.final_recommendation import FinalRecommendation
from app.domain.models.evidence.evidence_item import EvidenceItem
from app.domain.models.evidence.evidence_summary import EvidenceSummary
from app.domain.models.intermediate_finding import IntermediateFinding
from app.domain.models.memory.memory_candidate import MemoryCandidate
from app.domain.models.memory.memory_record import MemoryRecord
from app.domain.models.memory.session_memory import SessionMemory
from app.domain.models.planning.execution_plan import ExecutionPlan


class ExecutionState(BaseModel):
    """Canonical state container for a single run."""

    trace_id: str | None = None
    stage_history: list[str] = Field(default_factory=list)
    request_metadata: dict[str, Any] = Field(default_factory=dict)

    original_query: str
    user_goal: str | None = None
    task_type: TaskType | None = None
    workflow_pattern: WorkflowPattern | None = None
    project_context: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)

    planning_depth: PlanningDepth = PlanningDepth.NONE
    plan: ExecutionPlan | None = None
    sub_questions: list[str] = Field(default_factory=list)
    comparison_candidates: list[str] = Field(default_factory=list)
    initial_evidence_strategy: str | None = None

    retrieved_evidence: list[EvidenceItem] = Field(default_factory=list)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
    intermediate_findings: list[IntermediateFinding] = Field(default_factory=list)

    final_recommendation: FinalRecommendation | None = None
    action_items: list[ActionItem] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    confidence: float | None = None
    conclusion: ConclusionResult | None = None

    session_memory: SessionMemory | None = None
    loaded_memory_records: list[MemoryRecord] = Field(default_factory=list)
    memory_candidates: list[MemoryCandidate] = Field(default_factory=list)
