"""Tool Execution Layer request 的 domain model。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import ActionMode, FamilyName
from app.domain.models.retrieval import RecentRetrievalAttempt
from app.domain.models.tool_execution_layer.evidence_shape import EvidenceShape
from app.domain.models.tool_execution_layer.request_completion_evaluation_request import (
    FallbackPolicy,
)


class ToolExecutionLayerRequest(BaseModel):
    """Research Executor 调用 Tool Execution Layer 的单次请求输入。

    该模型是 Research Executor 面向 TEL 的公开输入边界，不是顶层 workflow stage 的
    ExecutionContext，也不是 family/tool/adapter 的原始请求。TEL 会用它依次完成：
    family selection、retrieval query generation、family execution、request completion evaluation
    以及有限 retry/fallback。当前项目中该模型整体有用：未来新版 Research Executor 会把
    task framing、retrieval intent、source constraints 和执行预算投影成这个 request。
    """

    target_problem: str = Field(
        description=(
            "必填字段。当前这次 Tool Execution Layer request 要解决的 retrieval 目标问题。"
            "当前项目中有用：FamilySelectionService 用它判断 family，RetrievalQueryGenerationService "
            "用它生成 query，RequestCompletionEvaluationService 和 RetrievalTrace 会保留它作为评估与证据处理语境。"
            "它应是经过 Research Executor 聚焦后的当前检索目标，而不是完整最终回答。"
        ),
    )
    action_mode: ActionMode = Field(
        default=ActionMode.EXTERNAL_ACQUISITION,
        description=(
            "可选字段，默认 external_acquisition。高层 acquisition 模式，用于限制 family selection 的初始范围。"
            "当前项目中有用：memory_backed_acquisition 会优先/限定 research_knowledge_recall；"
            "external_acquisition 会面向 docs_search、paper_search、web_search；any 允许在全部已注入 family 中选择。"
        ),
    )
    evidence_goal: str | None = Field(
        default=None,
        description=(
            "可选字段。描述本次希望获取 evidence 的目标，例如确认事实、补充实现依据、比较方案或验证最新状态。"
            "当前项目中有用：会传给 family selection 和 query generation，帮助 selected_family 与 generated_query "
            "更贴近 Research Executor 的证据意图；TEL 自身不判断 evidence sufficiency。"
        ),
    )
    evidence_shape: EvidenceShape | None = Field(
        default=None,
        description=(
            "可选字段。期望 evidence 的形态，类型为 EvidenceShape。当前项目中有用：TEL 会把它传给 "
            "FamilySelectionService 和 RetrievalQueryGenerationService；同时从 evidence_shape.freshness_requirement "
            "派生 docs_search / web_search family request 的 freshness_requirement。该对象当前包含 "
            "desired_evidence_kind、freshness_requirement、breadth 三个字段。"
        ),
    )
    task_framing: str | None = Field(
        default=None,
        description=(
            "可选字段。上游对当前任务的 framing 或上下文说明，例如“这是实现任务的资料检索”或“复用已有研究记忆”。"
            "当前项目中有用：family selection 可用它识别已有知识复用倾向，query generation 会读取它以避免 query "
            "偏离当前任务边界。TEL 不直接解析复杂 planner 结构，只把该文本作为轻量语义信号传递。"
        ),
    )
    allowed_source_families: list[FamilyName] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。允许参与本次 selection 的 source family 白名单。当前项目中有用："
            "TEL 会把它传给 FamilySelectionService 和 RequestCompletionEvaluationService，用于限制初选和 "
            "cross-family fallback 候选。为空表示不额外限制，但仍会受已注入 family、available_families 和 blocked_source_families 约束。"
        ),
    )
    preferred_source_families: list[FamilyName] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。Research Executor 提供的 family 偏好顺序。当前项目中有用："
            "FamilySelectionService 会优先考虑这里列出的 family，但仍必须满足 allowed/blocked/available 约束。"
            "它只是偏好，不是强制选择。"
        ),
    )
    blocked_source_families: list[FamilyName] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。本次请求禁止选择的 family。当前项目中有用：TEL 初始 selection 会传入该列表；"
            "发生 fallback_to_broader_search 时，TEL 还会在内部把刚失败/无结果的 family 加入 blocked 集合，避免立刻回到同一 family。"
        ),
    )
    available_families: list[FamilyName] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。Research Executor 或运行时声明的当前可用 family。当前项目中有用："
            "TEL 会先与实际注入的 family services 求交集，得到 effective_available_families，再交给 selection/evaluation。"
            "为空时表示使用当前 TEL 实例中已注入的 family services。"
        ),
    )
    success_hint: str | None = Field(
        default=None,
        description=(
            "可选字段。描述“什么样的 retrieval result 算有用”的提示。当前项目中有用："
            "RetrievalQueryGenerationService 会把它放入 prompt，辅助 LLM 生成更可执行的 query。"
            "TEL/evaluator 当前不直接依据该字段判断完成度。"
        ),
    )
    recent_low_value_queries: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。近期效果较差、应避免重复使用的 query 表达。当前项目中有用："
            "RetrievalQueryGenerationService 会读取并最多使用前几条作为负面示例，降低重复低价值检索的概率。"
            "这些字符串不是历史 retrieval result，只是 query phrasing hint。"
        ),
    )
    recent_retrieval_attempts: list[RecentRetrievalAttempt] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。由 Research Executor 从先前 iteration 压缩并传入的近期 retrieval 尝试。"
            "当前项目中有用：TEL 在已选择 family 后，会从同一 target_problem、同一 family 且明确低价值的 "
            "attempt 派生 query 负例，降低重复无效 query 的概率。每项包含 coverage target、family/tool、"
            "query、执行状态、实际效用和 fallback 标记；它不是 raw trace，也不直接决定高层 memory/external 路径。"
            "旧调用方可继续只传 recent_low_value_queries。"
        ),
    )
    preferred_tool: str | None = Field(
        default=None,
        description=(
            "可选字段。Research Executor 拥有的 preferred tool hint。当前项目中有用：TEL 只会把它原样透传给被选中的 "
            "family request，由 family service 在自己的 tool registry 内决定是否使用。TEL 不会根据上一次 "
            "family_execution_result.selected_tool 自行设置、覆盖或推断 preferred_tool，也不会在顶层选择 concrete tool。"
        ),
    )
    source_names: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。docs_search 的子来源约束。当前项目中有用：TEL 会把它映射为 "
            "DocsSearchFamilyRequest.sub_source_types，用来限制 docs adapter 搜索哪些 docs 子来源，例如 openai_api、"
            "anthropic_api、claude_code 等。字段名 source_names 是 TEL request 里的历史命名；语义上更接近 docs sub_source_types，"
            "不是 SourceReference.source_type，也不是 publisher。"
        ),
    )
    include_domains: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。web_search 的 include domain 白名单。当前项目中有用：TEL 会透传给 "
            "WebSearchFamilyRequest.include_domains，最终约束 web search tool/adapter 的开放网页检索范围。"
            "仅适用于 web_search family，其它 family 会忽略。"
        ),
    )
    exclude_domains: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。web_search 的 exclude domain 黑名单。当前项目中有用：TEL 会透传给 "
            "WebSearchFamilyRequest.exclude_domains，避免搜索特定站点或来源。仅适用于 web_search family。"
        ),
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description=(
            "可选字段，默认 5，必须大于等于 1。单次 family search 期望返回的最大搜索结果数。"
            "当前项目中有用：TEL 会传给 docs_search、paper_search、web_search family request，用于控制 adapter/search "
            "阶段的结果规模。它不是 completion evaluator 的 max_results guard，也不直接表示最终 evidence unit 数量。"
        ),
    )
    max_content_fetches: int = Field(
        default=3,
        ge=0,
        description=(
            "可选字段，默认 3，必须大于等于 0。web_search / paper_search 中允许进一步抓取正文内容的最大候选数。"
            "当前项目中有用：TEL 会传给 paper_search 和 web_search family request；docs_search 和 memory recall 不使用。"
            "0 表示只使用 search result/snippet，不做正文 fetch。"
        ),
    )
    min_score_threshold: float = Field(
        default=0.5,
        ge=0.0,
        description=(
            "可选字段，默认 0.5，必须大于等于 0。web_search 中选择 content fetch candidate 的最低分数阈值。"
            "当前项目中有用：TEL 会传给 WebSearchFamilyRequest.min_score_threshold，web tool 用它决定哪些搜索结果值得进一步 fetch。"
            "它不影响 docs/paper/memory family。"
        ),
    )
    owner_user_id: str | None = Field(
        default=None,
        description=(
            "可选字段，但当 selected_family 为 research_knowledge_recall 时实际必需。当前项目中有用："
            "TEL 会在执行 memory family 前校验该字段；ResearchKnowledgeRecallFamilyRequest / memory tool 会用它作为用户所有权边界，"
            "避免跨用户召回记忆。它不是 source author，也不会写入 SourceReference。"
        ),
    )
    query_embedding: list[float] | None = Field(
        default=None,
        min_length=1,
        description=(
            "可选字段。Research Executor 预先计算好的 query embedding。当前项目中有用：当 research_knowledge_recall 被选中时，"
            "TEL 会把它透传给 memory family/tool；如果为空，ResearchKnowledgeMemoryTool 会尝试基于 query_text 调 embedding 服务生成。"
            "该列表元素为浮点 embedding 向量，不是 dict。"
        ),
    )
    project_scope_id: str | None = Field(
        default=None,
        description=(
            "可选字段。memory recall 的项目范围过滤条件。当前项目中有用：TEL 会传给 "
            "ResearchKnowledgeRecallFamilyRequest.project_scope_id，用于限制只召回某个 project scope 下的 research knowledge。"
            "仅适用于 research_knowledge_recall family。"
        ),
    )
    allowed_visibility_scopes: list[str] = Field(
        default_factory=lambda: ["user"],
        description=(
            "可选字段，默认 ['user']。memory recall 允许访问的 visibility scope 列表。当前项目中有用："
            "TEL 会透传给 memory family/tool，store 层据此限制可召回 knowledge unit 的可见性，例如 user、project、team 等。"
            "具体 scope 取值由 memory 存储和权限语义决定。"
        ),
    )
    knowledge_types: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。memory recall 的 knowledge type 过滤条件。当前项目中有用：TEL 会透传给 "
            "ResearchKnowledgeRecallFamilyRequest.knowledge_types，用于只召回特定类型的 knowledge，例如 fact、summary、decision 等。"
            "为空表示不按 knowledge type 额外过滤。"
        ),
    )
    topic_tags: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。memory recall 的 topic tag 过滤条件。当前项目中有用：TEL 会透传给 "
            "ResearchKnowledgeRecallFamilyRequest.topic_tags，用于缩小 reusable knowledge 的主题范围。"
            "为空表示不按 topic tag 额外过滤。"
        ),
    )
    source_types: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。memory recall 的原始来源类型过滤条件。当前项目中有用：TEL 会透传给 "
            "ResearchKnowledgeRecallFamilyRequest.source_types，用于筛选由特定原始 source type distill 出来的 knowledge unit，"
            "例如 web_page、paper、document 等。这里的 source_types 是 memory filter，不是 TEL family 名称。"
        ),
    )
    memory_recall_limit: int = Field(
        default=5,
        ge=1,
        description=(
            "可选字段，默认 5，必须大于等于 1。research_knowledge_recall 最多召回的 knowledge unit 数量。"
            "当前项目中有用：TEL 会映射为 ResearchKnowledgeRecallFamilyRequest.limit，控制 memory recall 的输出规模。"
        ),
    )
    retry_budget: int = Field(
        default=1,
        ge=0,
        description=(
            "可选字段，默认 1，必须大于等于 0。TEL 在同一个 bounded request 内允许执行 retry_same_tool 的最大次数。"
            "当前项目中有用：RequestCompletionEvaluationService 会读取它判断 retry 是否可用；TEL 会在内部维护 retry_count，"
            "并把最终计数写入 ToolExecutionLayerResult.execution_summary。该字段不是由调用方传入的当前 retry_count。"
        ),
    )
    fallback_policy: FallbackPolicy = Field(
        default="fallback_within_same_family",
        description=(
            "可选字段，默认 fallback_within_same_family。本次 request 的 fallback 策略。当前项目中有用："
            "TEL 会传给 RequestCompletionEvaluationService，用于判断 no_result/failed 后是否允许 same-family fallback 或 "
            "broader-family fallback。TEL v1 不伪造同 family alternative tool selection；fallback_to_broader_search "
            "可触发重新选择 family 并重新生成 query。"
        ),
    )
    timeout_limit_ms: int | None = Field(
        default=None,
        gt=0,
        description=(
            "可选字段，提供时必须大于 0。TEL request 的总超时预算，单位毫秒。当前项目中有用但 v1 仍较轻量："
            "TEL 会把它传给 RequestCompletionEvaluationService 作为 recovery guard；当前 request 不由调用方传入 "
            "request_elapsed_ms，若未来要严格执行耗时预算，应由 TEL 内部度量 elapsed time。"
        ),
    )


ExecutionStatus = Literal["completed", "failed"]
