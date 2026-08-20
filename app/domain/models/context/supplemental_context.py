"""当前 run 可访问的分区 supporting context。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models.context.context_item import ContextItem


class SupplementalContext(BaseModel):
    """当前 run 中被选择但未吸收到 RunningState 的支持性上下文。

    SupplementalContext 用于保存当前 run 可用的 supporting summaries。它按来源/用途分区，
    避免把所有 supporting material 堆进一个 loose list。这里的 ContextItem 应该是摘要级、
    可直接消费的上下文，不应默认存放完整 transcript、raw tool output 或外部文档全文。
    """

    session_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。来自 session / thread continuity 的支持性上下文。当前项目中有用："
            "ContextMemoryLoader 会把 session working summary、current local task framing、latest recommendation、"
            "latest action items 等整理成 ContextItem 放入这里。当前默认 pipeline 中它主要服务 planning、"
            "ConclusionGenerator 和 session continuity-aware output；TaskInterpreter 在 session memory 加载前执行，"
            "因此不会直接消费该字段。"
        ),
    )
    project_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。来自 project profile 或项目背景记忆的支持性上下文。当前项目中有用："
            "ContextMemoryLoader 会把 active project profile 摘要放入这里，并可能同步吸收部分摘要到 RunningState.project_context_summary。"
            "该分区用于 project grounding，不应放完整项目文档。"
        ),
    )
    decision_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。来自 decision memory 的支持性上下文。当前项目中有用：ContextMemoryLoader "
            "会把 active decisions 的摘要放入这里，Planner / ResearchExecutor / ConclusionGenerator 可用它避免重复评估已确定决策。"
            "完整 decision record 不应直接放入该字段。"
        ),
    )
    action_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。来自 action memory 或当前执行状态的支持性上下文。当前项目中有用："
            "ContextMemoryLoader 会把 active actions 的摘要放入这里，ACTION_PLANNING / TRACKING 任务可用它理解当前进展、阻塞和下一步。"
        ),
    )
    policy_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。来自 preference / policy memory 的支持性上下文。当前项目中有用："
            "ContextMemoryLoader 会把适用于当前 task/project 的偏好、约束或策略摘要放入这里，供 planning 和 output 阶段参考。"
        ),
    )
    research_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。来自 research knowledge memory 的支持性上下文。当前项目中有用：ContextMemoryLoader "
            "会把召回到的 reusable research knowledge 摘要放入这里；ResearchExecutor 可据此优先尝试 memory-backed acquisition "
            "或将其作为当前 research 的背景信号。该字段保存的是已沉淀知识摘要，不是新的 raw external evidence。"
        ),
    )
    external_evidence_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。来自当前 run 或上游已筛选外部 evidence 的支持性上下文。"
            "当前默认 pipeline 暂未生产或消费该字段，保留它是为了后续将少量高优先级 external evidence summary "
            "交给 ConclusionGenerator 等阶段；该字段不应成为 raw retrieval results 或完整网页/论文正文的存放位置。"
        ),
    )
