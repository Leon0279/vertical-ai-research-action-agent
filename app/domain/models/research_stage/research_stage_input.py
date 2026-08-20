"""Research Stage 的显式输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models.context.context_item import ContextItem


class ResearchStageInput(BaseModel):
    """Research Executor 在 stage 内实际消费的输入子集。

    ResearchStageInput 由 ResearchActionPipeline 在 research stage 入口处从
    ExecutionContext 投影生成。它不是完整 ExecutionContext，也不负责保存 stage 运行后的结果。
    """

    original_query: str = Field(
        min_length=1,
        description="必填字段。用户原始 query，作为 research stage 的最终 fallback objective。",
    )
    task_type: str | None = Field(
        default=None,
        description="可选字段。上游 Task Interpretation 解析出的任务类型，用于后续 research 策略选择。",
    )
    user_goal: str | None = Field(
        default=None,
        description="可选字段。用户目标摘要，可作为 research objective 的主要语义来源。",
    )
    task_framing: str | None = Field(
        default=None,
        description="可选字段。当前任务的高层 framing，用于约束 research stage 的执行语境。",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。当前 run 中对 research stage 生效的显式约束。",
    )
    project_scope_id: str | None = Field(
        default=None,
        description="可选字段。当前 run 的项目范围 ID，可用于后续 memory recall 或 project-scoped retrieval。",
    )
    owner_user_id: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 的用户归属 ID，通常由 ResearchActionPipeline 从 RuntimeContext.user_id 投影而来。"
            "当前项目中有用：ResearchExecutorService 在触发 memory-backed acquisition 时，会把它传给 "
            "ToolExecutionLayerRequest.owner_user_id，供 research_knowledge_recall family 做用户级 memory recall 边界校验。"
            "它不是 source author，也不应写入 SourceReference。"
        ),
    )
    project_context_summary: str | None = Field(
        default=None,
        description="可选字段。项目背景摘要，用于让 research stage 在项目语境内选择 evidence need。",
    )
    plan: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。Planning 阶段产出的高层执行计划，作为 research guidance。",
    )
    sub_questions: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。Planning 阶段拆解出的子问题，后续可作为 research iteration target。",
    )
    comparison_candidates: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。Comparison 任务中的候选对象列表。",
    )
    information_gaps: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。当前已识别的信息缺口，后续可作为 retrieval / evidence target。",
    )
    initial_evidence_strategy: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。Planning 阶段给出的初始 evidence gathering guidance。"
            "当前项目中有用：ResearchExecutorService 会把它作为 assessment 的 planning reference，"
            "帮助判断下一步 evidence need 是否符合当前任务类型、项目约束与既有规划。"
        ),
    )
    active_decision_summary: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 project scope 内仍会影响本次研究的关键决策摘要。"
            "当前项目中有用：ResearchExecutorService 会在 assessment 中将它作为已有决策约束，"
            "避免把已经确定的方向错误识别为待重新研究的问题。"
        ),
    )
    current_action_status: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 project scope 的行动或执行状态摘要。当前项目中有用："
            "ResearchExecutorService 会把它作为 ACTION_PLANNING/TRACKING assessment 的状态输入，"
            "用于识别阻塞、进展和 actionability gap。"
        ),
    )
    current_bottleneck_summary: str | None = Field(
        default=None,
        description=(
            "可选字段。当前项目或任务最关键瓶颈的摘要。当前项目中有用："
            "ResearchExecutorService 会将它作为 research objective 的优先级校准信息，"
            "但不会仅凭该字段扩大原始研究范围。"
        ),
    )
    existing_intermediate_findings: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。进入 research stage 前已有的中间发现。",
    )
    research_support: list[ContextItem] = Field(
        default_factory=list,
        description="可选字段，默认空列表。已筛选的 research knowledge supporting context。",
    )
    decision_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。来自 SupplementalContext.decision_support 的已蒸馏 decision 摘要材料。"
            "当前用于 ResearchExecutor 评估当前研究是否受已有决策约束、是否存在决策支撑不足或冲突；"
            "它不是 raw decision record，也不是本轮 retrieval evidence。"
        ),
    )
    action_support: list[ContextItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。来自 SupplementalContext.action_support 的已蒸馏 action / execution status "
            "摘要材料。当前用于 ResearchExecutor 判断行动状态、阻塞、下一步可执行性相关 gap；"
            "它不是 raw action record，也不是本轮 retrieval evidence。"
        ),
    )
    available_tools: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。当前 runtime 声明可供 research stage 使用的工具或能力标识。",
    )
    latency_budget_ms: int | None = Field(
        default=None,
        description="可选字段。当前 run 可传递给 research stage 的延迟预算，单位毫秒。",
    )
    iteration_budget: int | None = Field(
        default=None,
        description="可选字段。当前 research stage 的迭代预算上限。",
    )
    scope_restrictions: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。当前 runtime 对 research stage 施加的访问或行动范围限制。",
    )
