"""Domain model for individual plan steps."""

from typing import Literal

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """A single executable planning step."""

    step_id: str = Field(description="必填字段。计划步骤在当前 ExecutionPlan 内的稳定标识。")
    title: str = Field(description="必填字段。步骤的简短名称，说明该步骤要完成的工作。")
    description: str | None = Field(
        default=None,
        description="可选字段。步骤目标、执行边界或预期产出的详细说明；没有补充时为 None。",
    )
    status: Literal["pending", "in_progress", "done"] = Field(
        default="pending",
        description="步骤当前状态：pending 表示未开始，in_progress 表示进行中，done 表示已完成。",
    )
