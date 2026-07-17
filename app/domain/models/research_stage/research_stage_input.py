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
