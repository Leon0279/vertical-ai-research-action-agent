"""Domain model for execution plans."""

from pydantic import BaseModel, Field

from app.domain.enums.planning_depth import PlanningDepth
from app.domain.models.planning.plan_step import PlanStep


class ExecutionPlan(BaseModel):
    """表示执行计划。

Structured plan for current run."""

    objective: str = Field(description="必填字段。当前执行计划要达成的目标，应与用户目标或当前任务范围对齐。")
    planning_depth: PlanningDepth = Field(
        default=PlanningDepth.SHALLOW,
        description="计划采用的拆解深度；当前默认 SHALLOW，用于表达仅生成轻量执行步骤。",
    )
    steps: list[PlanStep] = Field(
        default_factory=list,
        description="可选字段，默认空列表。按顺序执行或参考的结构化计划步骤。",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。计划执行时需要保留的补充注意事项，不应放原始工具输出。",
    )
