"""单次 request run 的核心可变状态模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums.planning_depth import PlanningDepth
from app.domain.enums.workflow_pattern import WorkflowPattern
from app.domain.models.citation import Citation
from app.domain.models.research_stage.research_stage_result import ResearchStageStatus
from app.domain.models.source import SourceReference
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
            "可选字段。当前项目或任务最关键瓶颈的摘要。当前项目中有用但不一定每轮都有值："
            "TaskInterpreterService 仅在用户明确描述阻塞、风险、性能瓶颈或推进困难时写入；Planner、ResearchExecutor 和 "
            "ConclusionGenerator 可据此校准优先级。该字段应是稳定瓶颈摘要，不是系统自行猜测的临时问题。"
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

    retrieved_evidence_refs: list[SourceReference] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 已采纳 evidence 的正式 typed 来源引用列表。当前项目中有用："
            "ResearchExecutor 会从 ProcessedEvidenceUnit.source_references 直接收集 SourceReference 并去重追加，"
            "pipeline 会把 ResearchStageResult.retrieved_evidence_refs 原样回写到该字段。该字段只保存来源 provenance，"
            "例如 source_type、source_id/source_id_type、source_url、title、authors、publisher、published_at、evidence_span "
            "和 metadata；不保存 evidence 正文、raw retrieval payload 或完整 ProcessedEvidenceUnit。需要展示 URL、typed id "
            "或 citation label 时，应由调用方从 SourceReference 派生。"
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
    research_status: ResearchStageStatus | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 的 Research Stage 顶层状态。当前项目中有用："
            "ResearchActionPipeline 会从 ResearchStageResult 回写该字段；"
            "ConclusionGeneratorService 据此决定是否必须返回确定性降级答案，"
            "ResponseAssemblerService 会在安全 metadata 中输出该状态。Research Stage 尚未执行时为 None。"
        ),
    )
    research_iteration_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0。当前 run 的 Research Executor 实际完成的 iteration 数量。"
            "当前项目中有用：ResearchActionPipeline 从 ResearchStageResult 回写，"
            "ResponseAssemblerService 在 metadata 中输出该值，便于调用方了解 research loop 的实际执行规模。"
        ),
    )

    final_answer: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 最终给用户看的完整自然语言答案。当前项目中有用："
            "ConclusionGeneratorService 会基于 original_query、task framing、research evidence、intermediate findings、"
            "open questions 和少量 distilled supporting context 生成该字段；ResponseAssemblerService 会把它输出到 "
            "StructuredOutput.answer。它不是由 final_summary、final_recommendation 或 action_items 机械拼接出来的，"
            "而是面向用户阅读的一段完整正文。research 阶段不应写该字段；如果 conclusion 阶段失败或尚未运行，"
            "该字段通常为 None。"
        ),
    )
    final_summary: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 最终答案的短摘要、TL;DR 或 UI 预览文案。当前项目中有用："
            "ConclusionGeneratorService 会写入该字段；ResponseAssemblerService 会优先把它映射到 StructuredOutput.summary；"
            "未来 session continuity、memory distillation、列表页预览或通知摘要也可以使用它。它不替代 final_answer，"
            "也不应承载完整推理过程或完整 evidence 列表。"
        ),
    )
    final_recommendation: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 收敛后的结构化主推荐、主判断或主结论短句。当前项目中有用："
            "ConclusionGeneratorService 会在 recommendation、decision、comparison、action_planning 等任务中写入；"
            "ResponseAssemblerService 会映射到 StructuredOutput.recommendation；MemoryDistillerService 和 session continuity "
            "会读取它生成 decision memory 或最近推荐记录。它不同于 final_answer：final_answer 是完整用户正文，"
            "final_recommendation 是便于下游结构化消费和检索的短句。纯事实问答或探索类任务可以为空。"
        ),
    )
    action_items: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 产出的用户可执行下一步行动项标题或简短描述。当前项目中有用："
            "ConclusionGeneratorService 会在 action_planning、recommendation、tracking 等任务中写入；"
            "ResponseAssemblerService 会把每个字符串转换为 ActionItem 输出；SessionContinuityManagerService 会把它保存到 "
            "session memory。未来该字段可用于 action memory、任务创建、提醒或 checklist。没有明确行动建议时保持空列表，"
            "不要为了填充结构而生成泛泛的行动项。"
        ),
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 最终答案实际引用的来源列表。当前项目中有用："
            "ConclusionGeneratorService 会从 retrieved_evidence_refs 可派生的来源 handle 中选择 citation 并写入；"
            "ResponseAssemblerService 会映射到 StructuredOutput.citations，帮助用户核验结论来源。citation 只保存展示级引用，"
            "不替代 RunningState.retrieved_evidence_refs 中的 typed SourceReference；不要让 LLM 编造不在 retrieved_evidence_refs "
            "里的来源。"
        ),
    )
    confidence: str | None = Field(
        default=None,
        description=(
            "可选字段。当前 run 最终答案的整体置信度标签，建议值为 low、medium 或 high。当前项目中有用："
            "ConclusionGeneratorService 会写入该字段；ResponseAssemblerService 会把它转换成数值 confidence；"
            "MemoryDistillerService 可把它作为 memory candidate 的稳定性信号。它表达最终答案在当前 evidence、"
            "open questions 和 caveats 下是否足够稳，不代表单条 evidence 的 provider score。未形成结论前通常为 None。"
        ),
    )
    caveats: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前 run 最终答案的限制条件、未覆盖范围、风险提示或仍未解决的问题。当前项目中有用："
            "ConclusionGeneratorService 会把 ResearchExecutor 产生的 open_questions、evidence 不足、冲突或新鲜度限制转成用户可理解的 "
            "caveats；ResponseAssemblerService 会输出到 StructuredOutput.caveats。它不是 debug trace，也不应保存 raw error payload；"
            "如果没有需要提醒用户的限制，可保持空列表。"
        ),
    )
