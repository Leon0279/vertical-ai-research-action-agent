"""单次 request run 的核心可变状态模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums.planning_depth import PlanningDepth
from app.domain.enums.workflow_pattern import WorkflowPattern
from app.domain.models.workflow_execution_policy import WorkflowExecutionPolicy


class RunningState(BaseModel):
    """当前 run 的 canonical mutable state。

    RunningState 只承载会被多个 workflow stage 持续读取、更新或用于最终输出的核心工作变量。
    它不用于存放完整 transcript、raw tool payload、完整外部资料或未筛选的大段 supporting material；
    这些内容应优先放在 SupplementalContext 或下游专门的 result/provenance 模型中。
    """

    original_query: str = Field(
        min_length=1,
        description=(
            "必填字段，不能为空字符串。用户在当前 run 中提交的原始 query。当前项目中有用："
            "RequestIntakeService 初始化该字段；TaskInterpreter、Planner、ResearchExecutor 等 stage 会把它作为 "
            "fallback objective 或语义锚点。该字段应保留用户原话，不应被后续 stage 改写成总结或解释。"
        ),
    )
    task_type: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 的顶层任务类型。当前项目中有用：TaskInterpreterService 会写入该字段，"
            "WorkflowRouter、Planner、ResearchExecutor、ResponseAssembler 等后续 stage 会读取它决定 workflow pattern、"
            "planning depth、evidence goal 和输出形态。典型值来自 TaskType，例如 TOPIC_EXPLORATION、COMPARISON、"
            "RECOMMENDATION、ACTION_PLANNING、TRACKING。未解释前为 None。"
        ),
    )
    user_goal: str | None = Field(
        default=None,
        description=(
            "可选字段。当前请求背后的用户目标或意图摘要。当前项目中有用：TaskInterpreterService 会尝试从 original_query "
            "中提炼该字段；Planner 和 ResearchExecutor 会把它作为 objective / target fallback。它应是简短目标表达，"
            "不是完整最终答案。"
        ),
    )
    task_framing: str | None = Field(
        default=None,
        description=(
            "可选字段。当前问题应如何处理的高层 framing。当前项目中有用：TaskInterpreter、ContextMemoryLoader "
            "和 Planner 可能写入或保留该字段；ResearchExecutor 会把它传给 ToolExecutionLayerRequest.task_framing，"
            "辅助 family selection 和 query generation。示例包括 project_specific_recommendation、"
            "engineering_tradeoff_comparison、implementation_planning 等。"
        ),
    )
    constraints: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 中明确生效的约束。当前项目中有用：TaskInterpreter 会写入用户显式约束，"
            "ContextMemoryLoader 可能从 project profile 合并项目约束；Planner、ConclusionGenerator 和后续输出阶段可据此收窄建议。"
            "列表元素应是简短可读约束文本，不应放入复杂 raw config。"
        ),
    )

    project_scope_id: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 解析出的 project scope 标识。当前项目中有用：RequestIntake 或上游 context 可设置该字段；"
            "ContextMemoryLoader 用它加载 project profile、active decisions/actions；ResearchExecutor 会把它传给 memory recall "
            "相关 request 作为项目范围过滤。没有项目边界时为 None。"
        ),
    )
    project_context_summary: str | None = Field(
        default=None,
        description=(
            "可选字段。当前项目背景与上下文的摘要。当前项目中有用：TaskInterpreter 可从用户 query 中提取显式项目背景，"
            "ContextMemoryLoader 可从 project profile 填充；Planner 和 ConclusionGenerator 可用它让研究或建议贴合当前项目。"
            "该字段应保持摘要级，不应放完整项目文档。"
        ),
    )
    current_bottleneck_summary: str | None = Field(
        default=None,
        description=(
            "可选字段。当前项目或任务最关键瓶颈的摘要。当前项目中有用但不一定每轮都有值：Planner 可用它调整推荐/行动计划方向，"
            "ConclusionGenerator 可用它解释优先级。该字段应是稳定瓶颈摘要，不是临时推测。"
        ),
    )
    active_decision_summary: str | None = Field(
        default=None,
        description=(
            "可选字段。当前仍然有效且会影响本次 run 的关键决策摘要。当前项目中有用：ContextMemoryLoader 从 active decision "
            "memory 中提炼写入；Planner、ResearchExecutor 和 ConclusionGenerator 可用它避免重复评估已确定的方向。"
            "该字段不应保存完整 decision record。"
        ),
    )
    current_action_status: str | None = Field(
        default=None,
        description=(
            "可选字段。当前项目行动或执行状态摘要。当前项目中有用：ContextMemoryLoader 可从 action memory 填充；"
            "ACTION_PLANNING / TRACKING 类任务会读取它来生成更贴近当前进展的计划或更新。没有相关状态时为 None。"
        ),
    )

    workflow_pattern: WorkflowPattern | None = Field(
        default=None,
        description=(
            "可选字段。WorkflowRouter 为当前 run 选择的 workflow pattern。当前项目中有用：ResponseAssembler "
            "会优先使用该字段输出 workflow_pattern；后续 stage 也可用它判断当前任务走 topic exploration、comparison、"
            "recommendation、action planning 或 tracking 变体。路由前为 None。"
        ),
    )
    execution_policy: WorkflowExecutionPolicy | None = Field(
        default=None,
        description=(
            "可选字段。WorkflowRouter 选择的轻量执行策略对象。当前项目中有用：Planner 会读取其中的 planning_depth、"
            "evidence_strategy 等字段来决定规划深度和初始证据姿态。该对象不是完整 workflow definition，"
            "只表达当前 run 的轻量执行偏好。"
        ),
    )

    planning_depth: PlanningDepth = Field(
        default=PlanningDepth.NONE,
        description=(
            "可选字段，默认 PlanningDepth.NONE。当前 run 的规划深度。当前项目中有用：DecompositionPlannerService "
            "会根据 task_type / execution_policy 设置该字段，并据此决定是否生成 plan、sub_questions、comparison_candidates 等。"
        ),
    )
    plan: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 的执行计划步骤。当前项目中有用：DecompositionPlannerService 会写入简短计划项，"
            "ResearchExecutor 和 downstream stages 可把它作为 research/execution guidance。列表项应是可读步骤文本，"
            "不是嵌套任务对象。"
        ),
    )
    sub_questions: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 拆解出的子问题。当前项目中有用：DecompositionPlannerService 会写入该字段；"
            "ResearchExecutor 会优先把它作为逐轮 retrieval target。为空时 ResearchExecutor 会退回 information_gaps、user_goal 或 original_query。"
        ),
    )
    comparison_candidates: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前比较任务中的候选对象。当前项目中有用：Planner 会从 query 中提取候选项；"
            "ResearchExecutor / EvidenceProcessing 可通过 retrieval context 将 evidence 关联到候选对象；ConclusionGenerator "
            "后续可用它生成结构化对比。非 comparison 任务通常为空。"
        ),
    )
    information_gaps: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前已识别但尚未补齐的信息缺口。当前项目中有用：Planner 会写入初始 gap；"
            "ResearchExecutor 在没有 sub_questions 时会把它作为 retrieval target；research 过程中也可追加未解决问题。"
        ),
    )
    initial_evidence_strategy: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。Planning 阶段生成的初始 evidence gathering guidance。当前项目中有用："
            "DecompositionPlannerService 会根据 task_type、project context、active decisions 等生成提示，例如优先查对比证据、"
            "fresh status、dependencies 或 actionability signals。它是 research guidance，不是最终 evidence。"
        ),
    )

    retrieved_evidence_refs: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 已采纳 evidence 的轻量引用字符串。当前项目中有用：ResearchExecutor "
            "会从 ProcessedEvidenceUnit.source_references 派生 URL、typed id 或标题并去重追加。该字段只放引用/handle，"
            "不放大段 evidence 正文；完整 typed provenance 仍在 evidence processing 输出中。"
        ),
    )
    evidence_summary: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 累积 evidence layer 的摘要。当前项目中有用：ResearchExecutor 会写入本轮 processed evidence "
            "数量、type breakdown、source coverage 和处理状态；ConclusionGenerator / MemoryDistiller 可读取它作为下游摘要输入。"
            "该字段是 human-readable summary，不是结构化 evidence store。"
        ),
    )
    intermediate_findings: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 中形成的中间发现或临时判断。当前项目中有用：ResearchExecutor v1 "
            "会将 processed evidence content 作为 evidence-backed provisional findings 写入；后续 ConclusionGenerator "
            "可基于这些 finding 做 final synthesis。列表项应是简短 source-grounded statement。"
        ),
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 仍未解决的问题、失败原因或待补 gap。当前项目中有用：ContextMemoryLoader "
            "可从 session memory 合并 open questions；ResearchExecutor 会在 TEL failed/no_result、EvidenceProcessing failed/no_result "
            "或 iteration budget exhausted 时追加说明。"
        ),
    )

    final_recommendation: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 收敛后的最终推荐文本。当前项目中有用：ConclusionGeneratorService 会写入该字段；"
            "ResponseAssembler 和 MemoryDistiller 会读取它生成结构化输出和 memory candidate。research 阶段不应直接写最终推荐。"
        ),
    )
    action_items: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 产出的行动项标题或简短描述。当前项目中有用：ConclusionGeneratorService "
            "会在行动计划或推荐类任务中写入；ResponseAssembler 会把它转换为 ActionItem 输出。"
        ),
    )
    confidence: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 最终输出的整体置信度标签。当前项目中有用：ConclusionGeneratorService 写入 low/medium/high "
            "等字符串；ResponseAssembler 和 MemoryDistiller 会把它转换成分数或持久化信号。未形成结论前通常为 None。"
        ),
    )
