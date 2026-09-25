"""Context Memory Loader Stage 的显式输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models.context.context_item import ContextItem


class ContextMemoryLoaderStageResult(BaseModel):
    """Context Memory Loader 返回给 pipeline 的显式阶段结果。"""

    task_framing: str | None = Field(
        default=None,
        description=(
            "可选字段。由 Session Memory 提供的 task framing 候选补充值；"
            "pipeline 仅在 Task Interpreter 未生成该字段时采用。"
        ),
    )
    project_context_summary: str | None = Field(
        default=None,
        description=(
            "可选字段。由 active Project Profile 提炼的项目背景候选补充值；"
            "pipeline 仅在 Task Interpreter 未生成该字段时采用。"
        ),
    )
    active_decision_summary: str | None = Field(
        default=None,
        description=(
            "可选字段。由 active Decision Memory 提炼的当前决策摘要；"
            "固定 pipeline 中此前没有该字段的生产者，因此由 pipeline 直接写入 RunningState。"
        ),
    )
    current_action_status: str | None = Field(
        default=None,
        description=(
            "可选字段。由 active Action Memory 提炼的当前行动状态；"
            "固定 pipeline 中此前没有该字段的生产者，因此由 pipeline 直接写入 RunningState。"
        ),
    )
    constraints: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。由 Project Profile Memory 提供的约束增量；"
            "pipeline 会将其与 Task Interpreter 已识别的用户约束去重合并。"
        ),
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。Context Memory Loader 从 Session Memory 加载的完整未解决问题列表；"
            "固定 pipeline 中此前没有该字段的生产者，因此由 pipeline 直接写入 RunningState。"
        ),
    )
    session_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。本阶段选中的完整 session continuity 摘要级支持材料；"
            "由 pipeline 直接写入 SupplementalContext.session_support。"
        ),
    )
    project_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。本阶段选中的完整 project profile 摘要级支持材料；"
            "由 pipeline 直接写入 SupplementalContext.project_support。"
        ),
    )
    decision_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。本阶段选中的完整 active decision 摘要级支持材料；"
            "由 pipeline 直接写入 SupplementalContext.decision_support。"
        ),
    )
    action_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。本阶段选中的完整 active action 摘要级支持材料；"
            "由 pipeline 直接写入 SupplementalContext.action_support。"
        ),
    )
    policy_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。本阶段选中的完整 preference/policy 摘要级支持材料；"
            "由 pipeline 直接写入 SupplementalContext.policy_support。"
        ),
    )
    research_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。本阶段召回并筛选出的完整 research knowledge 摘要级支持材料；"
            "由 pipeline 直接写入 SupplementalContext.research_support。"
        ),
    )
