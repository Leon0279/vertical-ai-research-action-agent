"""Retrieval Query Generation Service 的输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import FamilyName
from app.domain.models.tool_execution_layer.evidence_shape import EvidenceShape


class RetrievalQueryGenerationRequest(BaseModel):
    """在已选定 retrieval family 后生成 retrieval query 的标准化输入。

    该模型是 Tool Execution Layer 中 query generation 子服务的公开输入边界。它发生在
    FamilySelectionService 已经产出 selected_family 之后、family service 执行之前。当前项目中该模型有用：
    ToolExecutionLayerService 会用 selected_family 和当前 retrieval intent 构造它；RetrievalQueryGenerationService
    会把这些字段组织进中文 prompt，调用 LLM 生成适合后续 family retrieval 的 generated_query。

    重要边界：该模型不包含 selected_tool，不包含 max_results / timeout_limit_ms，不表达 executable request，
    也不负责选择 family 或执行 retrieval。tool selection 仍由各 family service 内部负责。
    """

    selected_family: FamilyName = Field(
        description=(
            "必填字段。FamilySelectionService 已经选出的 retrieval family。当前项目中有用："
            "RetrievalQueryGenerationService 会根据它选择 query wording 风格，例如 research_knowledge_recall 偏 reusable knowledge recall，"
            "docs_search 偏官方文档/API/config，paper_search 偏论文/方法/比较表达，web_search 偏开放网页/最新状态。"
            "该字段类型为 FamilyName，旧字符串输入仍可兼容转换；它只表示 family，不表示 concrete tool，"
            "query generation service 不得改变该值，也不得输出 selected_tool。"
        ),
    )
    target_problem: str = Field(
        description=(
            "必填字段。当前这轮 query generation 要服务的 retrieval 目标问题或证据缺口。当前项目中有用："
            "service 会 trim 该字段，并在为空时返回 generation_status='failed'；LLM prompt 会把它作为 query 的核心语义边界，"
            "要求生成 query 时不要改变 target_problem 的核心含义、不要引入新的 sub-question、不要把问题扩展成更宽 topic。"
            "该字段应是 Research Executor / TEL 已经聚焦后的检索目标，而不是最终答案或完整 ExecutionContext。"
        ),
    )
    evidence_goal: str | None = Field(
        default=None,
        description=(
            "可选字段。本轮希望 retrieval 结果达成的证据目标，例如 coverage、support、ambiguity、conflict、fresh status、"
            "comparison、actionability 等。当前项目中有用：RetrievalQueryGenerationService 会把它放入 prompt，"
            "让 LLM 调整 query 的检索重点；例如 refresh_status 应更适合 web_search，rebalance_comparison 应更强调比较对象或方法。"
            "该字段不是 enum，当前保持字符串以便上游 Research Executor / planner 渐进扩展目标语义。为空时，query 仍可仅基于 "
            "selected_family、target_problem、evidence_shape 等生成。"
        ),
    )
    evidence_shape: EvidenceShape | None = Field(
        default=None,
        description=(
            "可选字段。期望 evidence 的形态，类型为 EvidenceShape。当前项目中有用：service 会把它序列化进 LLM prompt，"
            "用于约束 query 风格；desired_evidence_kind 会影响 query 更偏直接事实、支持证据、消歧证据、比较证据还是状态证据；"
            "freshness_requirement 会影响是否强调 latest/current/status；breadth 会影响 query 偏窄命中还是宽覆盖。"
            "该对象已有独立中文字段注释；为空时不会阻止 query generation。"
        ),
    )
    success_hint: str | None = Field(
        default=None,
        description=(
            "可选字段。描述“什么样的 retrieval result 算有用”的轻量提示。当前项目中有用："
            "RetrievalQueryGenerationService 会把它放入 prompt，帮助 LLM 生成更贴近下游 retrieval 成功条件的 query。"
            "例如可以描述希望命中文档配置项、论文方法对比、最新产品状态或已有知识主题。该字段只辅助 query phrasing，"
            "不用于判断 retrieval 是否完成，也不生成 executable request。"
        ),
    )
    task_framing: str | None = Field(
        default=None,
        description=(
            "可选字段。上游对当前任务的 framing 或背景说明。当前项目中有用：service 会把它作为低优先级上下文放入 prompt，"
            "帮助 LLM 避免 query 偏离当前任务边界；例如说明这是实现任务、比较任务、状态核验任务或复用记忆任务。"
            "该字段不会覆盖 target_problem，也不会触发 family/tool selection。为空时不会影响基本 query generation。"
        ),
    )
    recent_low_value_queries: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。近期效果较差、应该避免重复使用的 query phrasing。当前项目中有用："
            "RetrievalQueryGenerationService 会 trim、去空、去重，并最多保留前 3 条放入 prompt，要求 LLM 不要直接重复这些表达。"
            "该字段只是 query wording 的负面提示，不是 retrieval attempt 完整历史，也不包含 family/tool execution result。"
            "列表元素是字符串，不是 dict。"
        ),
    )
