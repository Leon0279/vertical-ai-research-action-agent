"""Domain model for execution plans."""

from pydantic import BaseModel, Field

from app.domain.enums.planning_depth import PlanningDepth
from app.domain.models.planning.plan_step import PlanStep


class ExecutionPlan(BaseModel):
    """Structured plan for current run."""

    objective: str
    planning_depth: PlanningDepth = PlanningDepth.SHALLOW
    steps: list[PlanStep] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
