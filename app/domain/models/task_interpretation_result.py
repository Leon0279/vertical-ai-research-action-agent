"""Structured result produced by task interpretation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums.task_type import TaskType


class TaskInterpretationResult(BaseModel):
    """表示任务理解的处理结果。

Initial semantic interpretation of a normalized user request."""

    model_config = ConfigDict(extra="forbid")

    user_goal: str = Field(
        min_length=1,
        description="必填字段。由任务理解阶段从原始请求提炼出的用户目标，供后续 routing、planning 和 research 使用。",
    )
    task_type: TaskType = Field(description="必填字段。归一化后的任务类型，决定 workflow pattern 和下游处理倾向。")
    task_framing: str | None = Field(
        default=None,
        description="可选字段。当前任务应采用的高层处理 framing，例如对比、项目内推荐或实施规划。",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。从请求提取出的明确限制，用于收窄规划、研究和结论范围。",
    )
    project_context_summary: str | None = Field(
        default=None,
        description="可选字段。请求中明确提供的项目背景摘要；没有项目上下文时为 None。",
    )
    current_bottleneck_summary: str | None = Field(
        default=None,
        description=(
            "可选字段。用户请求中明确描述的当前项目或任务瓶颈摘要。当前项目中有用："
            "TaskInterpreterService 会把该字段写入 RunningState，供 Planner、Research Executor、"
            "ConclusionGenerator 和 memory 相关阶段了解当前最需要突破的问题。没有明确瓶颈时为 None；"
            "不得根据未提供的信息推测或虚构瓶颈。"
        ),
    )

    @field_validator(
        "user_goal",
        "task_framing",
        "project_context_summary",
        "current_bottleneck_summary",
        mode="before",
    )
    @classmethod
    def _strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("constraints", mode="before")
    @classmethod
    def _strip_constraints(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            return value
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
