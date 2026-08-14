"""Workflow execution policy selected by the workflow router."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums.memory_type import MemoryType
from app.domain.enums.planning_depth import PlanningDepth


class WorkflowExecutionPolicy(BaseModel):
    """Lightweight downstream execution policy produced by workflow routing."""

    model_config = ConfigDict(extra="forbid")

    planning_depth: PlanningDepth = Field(
        description="必填字段。下游规划阶段应优先采用的默认 planning depth。",
    )
    evidence_strategy: str = Field(
        min_length=1,
        description="必填字段。research execution 应强调的高层 evidence strategy。",
    )
    output_emphasis: str = Field(
        min_length=1,
        description="必填字段。conclusion generation 应侧重的高层输出结构或表达重点。",
    )
    memory_writeback_focus: list[MemoryType] = Field(
        default_factory=list,
        description="可选字段，默认空列表。下游 memory write-back 应重点考虑的长期 memory 类别。",
    )
    comparison_needed: bool = Field(
        default=False,
        description="下游 stage 是否应重点产出结构化比较；当前默认 False。",
    )
    recommendation_needed: bool = Field(
        default=False,
        description="下游 stage 是否应产出面向决策的 recommendation；当前默认 False。",
    )
    action_generation_needed: bool = Field(
        default=False,
        description="下游 stage 是否应产出下一步 action 项；当前默认 False。",
    )
    tracking_needed: bool = Field(
        default=False,
        description="下游 stage 是否应强调状态更新与 tracking；当前默认 False。",
    )
    routing_confidence: str = Field(
        min_length=1,
        description="必填字段。workflow router 对当前路由结果的置信度标签，例如 high 或 low。",
    )
    fallback_reason: str | None = Field(
        default=None,
        description="可选字段。router 退回保守 workflow 时的原因；未发生 fallback 时为 None。",
    )
