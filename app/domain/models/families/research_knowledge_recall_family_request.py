"""research_knowledge_recall family service 的运行时输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchKnowledgeRecallFamilyRequest(BaseModel):
    """ResearchKnowledgeRecallFamilyService.run(...) 使用的 family 层标准化请求。

    该模型不是 research_knowledge_memory tool 的请求，也不是 Postgres memory store 的原始查询对象；
    它位于 Tool Execution Layer 和具体 memory recall tool 之间。当前项目中通常由
    ToolExecutionLayerService 根据 selected_family、generated_query、runtime memory scope 和上游约束构造。
    ResearchKnowledgeRecallFamilyService 会负责选择 family 内部 tool，并把字段映射到
    ResearchKnowledgeMemoryToolRequest。
    """

    owner_user_id: str = Field(
        min_length=1,
        description=(
            "必填字段。research knowledge recall 的用户归属边界。当前项目中该字段有用："
            "ToolExecutionLayerService 在 selected_family=research_knowledge_recall 时要求上游提供 owner_user_id；"
            "ResearchKnowledgeRecallFamilyService 会去除首尾空白后透传给 ResearchKnowledgeMemoryToolRequest.owner_user_id；"
            "底层 PostgresResearchKnowledgeMemoryStore 会用它过滤 research_knowledge_units，确保只召回该用户可访问的 reusable research knowledge。"
        ),
    )
    query_text: str | None = Field(
        default=None,
        description=(
            "可选字段。用于 memory semantic recall 的文本 query。当前项目中该字段有用："
            "通常由 RetrievalQueryGenerationService 在 TEL 内生成，再由 ToolExecutionLayerService 写入 family request；"
            "ResearchKnowledgeRecallFamilyService 会透传给 ResearchKnowledgeMemoryToolRequest.query_text。"
            "如果 query_embedding 未提供，底层 ResearchKnowledgeMemoryTool 会用 query_text 调 embedding client 生成向量；"
            "如果 query_embedding 也为空，tool 会返回 failed。"
        ),
    )
    query_embedding: list[float] | None = Field(
        default=None,
        min_length=1,
        description=(
            "可选字段。上游已生成的语义向量。当前项目中该字段有用："
            "ToolExecutionLayerService / Research Executor 可在已有 query embedding 时传入，"
            "ResearchKnowledgeRecallFamilyService 会原样透传给 ResearchKnowledgeMemoryToolRequest.query_embedding；"
            "底层 tool 会优先复用该向量，不再调用 embedding client，并在 execution_summary.observability['used_precomputed_embedding'] "
            "中记录 True。列表至少包含 1 个 float。"
        ),
    )
    project_scope_id: str | None = Field(
        default=None,
        description=(
            "可选字段。项目级 recall scope。当前项目中该字段有用："
            "ToolExecutionLayerService 会从 ToolExecutionLayerRequest.project_scope_id 映射到这里；"
            "ResearchKnowledgeRecallFamilyService 会透传给 ResearchKnowledgeMemoryToolRequest.project_scope_id；"
            "Postgres recall path 会在有值时召回该 project scope 或全局为空 scope 的 knowledge，在无值时只召回 project_scope_id 为空的 knowledge。"
        ),
    )
    allowed_visibility_scopes: list[str] = Field(
        default_factory=lambda: ["user"],
        description=(
            "可选字段，默认 ['user']。本次 recall 允许访问的 visibility scope 列表。当前项目中该字段有用："
            "ResearchKnowledgeRecallFamilyService 会过滤空字符串后透传给 ResearchKnowledgeMemoryToolRequest.allowed_visibility_scopes；"
            "底层 tool 要求该列表非空，Postgres store 会用它约束 visibility_scope_effective。"
            "典型值包括 user、project、domain、global。该字段控制 memory recall 的访问边界，不是搜索关键词。"
        ),
    )
    knowledge_types: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。knowledge_type 过滤条件。当前项目中该字段有用："
            "非空时会透传给 ResearchKnowledgeMemoryToolRequest.knowledge_types，并最终进入 "
            "ResearchKnowledgeRecallQuery.knowledge_types；Postgres store 会用它过滤 knowledge_type。"
            "空列表表示不按 knowledge type 限制。常见值可包括 concept、method、comparison、conclusion、tradeoff、pattern "
            "或当前测试中使用的 engineering_observation。"
        ),
    )
    topic_tags: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。topic tag 过滤条件。当前项目中该字段有用："
            "非空时会透传给 ResearchKnowledgeMemoryToolRequest.topic_tags，并最终进入 ResearchKnowledgeRecallQuery.topic_tags；"
            "Postgres store 会用 research_knowledge_units.topic_tags 做过滤。空列表表示不按 topic tag 限制。"
            "该字段用于把语义召回限制在更相关的主题范围内，例如 postgresql、pgvector、retrieval。"
        ),
    )
    source_types: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。knowledge unit 的 primary source_type 过滤条件。当前项目中该字段有用："
            "非空时会透传给 ResearchKnowledgeMemoryToolRequest.source_types，并最终进入 ResearchKnowledgeRecallQuery.source_types；"
            "Postgres store 会用 ResearchKnowledgeUnitRecord.source_type 过滤。注意它不是 "
            "NormalizedRetrievalItem.source_references[*].source_type 的完整集合过滤，而是 research_knowledge_units 表上的 primary source_type。"
        ),
    )
    limit: int = Field(
        default=5,
        ge=1,
        description=(
            "可选字段，默认 5，必须大于等于 1。本次 family request 希望召回的 knowledge unit 数量上限。"
            "当前项目中该字段有用：ResearchKnowledgeRecallFamilyService 会透传给 ResearchKnowledgeMemoryToolRequest.limit；"
            "PostgresResearchKnowledgeMemoryStore 会再结合自身 config.max_recall_limit 做上限保护。"
            "该字段影响最终 normalized_items 的最大候选数量。"
        ),
    )
    preferred_tool: str | None = Field(
        default=None,
        description=(
            "可选字段。上游指定的 research_knowledge_recall family 内 preferred tool id。当前项目中该字段有用："
            "它只能由 Research Executor / ToolExecutionLayerService 作为 hint 原样传入；"
            "ResearchKnowledgeRecallFamilyService 只用它和 family 内部 tool registry 做匹配。若为空，则选择默认 "
            "research_knowledge_memory_v1；若非空但 registry 中不存在，family 返回 failed。family 不会根据上一次 selected_tool "
            "自行合成、覆盖或推断 preferred_tool。"
        ),
    )
