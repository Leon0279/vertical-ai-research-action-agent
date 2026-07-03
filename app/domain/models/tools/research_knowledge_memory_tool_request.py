"""research_knowledge_memory tool 的运行时输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchKnowledgeMemoryToolRequest(BaseModel):
    """research_knowledge_recall family 调用 research_knowledge_memory tool 时使用的标准化输入。

    该模型不是 PostgresResearchKnowledgeMemoryStore 的原始查询对象，而是 tool 层运行时请求。
    当前项目中它通常由 ResearchKnowledgeRecallFamilyService 根据 family request 构造；
    ToolExecutionLayerService 会在 memory-backed acquisition 路径中间接影响这些字段。
    """

    owner_user_id: str = Field(
        min_length=1,
        description=(
            "必填字段。research knowledge recall 的用户归属边界。当前项目中该字段有用："
            "ResearchKnowledgeMemoryTool 会在校验阶段要求它非空，并将它写入 "
            "ResearchKnowledgeRecallQuery.owner_user_id；PostgresResearchKnowledgeMemoryStore "
            "会用它过滤 research_knowledge_units，确保只召回该用户可访问的 reusable research knowledge。"
        ),
    )
    query_text: str | None = Field(
        default=None,
        description=(
            "可选字段。用于语义召回的文本 query。当前项目中该字段有用：当 query_embedding 未提供时，"
            "ResearchKnowledgeMemoryTool 会把规范化后的 query_text 传给 embedding client 生成 embedding；"
            "同时它会被写入 retrieval_trace.context['query_text']，供后续 Tool Execution Layer / "
            "EvidenceProcessingService 理解本次 memory recall 的检索语境。若 query_embedding 也为空，"
            "该字段必须非空，否则 tool 会返回 failed。"
        ),
    )
    query_embedding: list[float] | None = Field(
        default=None,
        min_length=1,
        description=(
            "可选字段。上游已预先生成的语义向量。当前项目中该字段有用：如果提供，"
            "ResearchKnowledgeMemoryTool 会直接复用它，不再调用 embedding client，并在 "
            "execution_summary.observability['used_precomputed_embedding'] 中记录 True；"
            "如果未提供，则由 query_text 生成 embedding。列表至少包含 1 个 float。"
        ),
    )
    project_scope_id: str | None = Field(
        default=None,
        description=(
            "可选字段。项目级 scope 约束。当前项目中该字段有用：ResearchKnowledgeMemoryTool "
            "会将它写入 ResearchKnowledgeRecallQuery.project_scope_id；Postgres recall path 会在有值时"
            "召回该 project scope 或全局为空 scope 的 knowledge，在无值时只召回 project_scope_id 为空的 knowledge。"
            "该字段也会写入 retrieval_trace.context['project_scope_id'] 作为 provenance。"
        ),
    )
    allowed_visibility_scopes: list[str] = Field(
        default_factory=lambda: ["user"],
        description=(
            "可选字段，默认 ['user']。本次 recall 允许访问的 visibility scope 列表。当前项目中该字段有用："
            "ResearchKnowledgeMemoryTool 会过滤空字符串并要求结果非空，然后写入 "
            "ResearchKnowledgeRecallQuery.allowed_visibility_scopes；Postgres store 会用它约束 "
            "visibility_scope_effective。典型值包括 user、project、domain、global。该字段会进入 "
            "retrieval_trace.context['allowed_visibility_scopes']，便于诊断为什么某些 memory 没有被召回。"
        ),
    )
    knowledge_types: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。knowledge_type 过滤条件。当前项目中该字段有用：非空时会写入 "
            "ResearchKnowledgeRecallQuery.knowledge_types，Postgres store 会用它过滤 knowledge_type；"
            "空列表表示不按 knowledge type 限制。常见值可包括 concept、method、comparison、conclusion、"
            "tradeoff、pattern 或当前项目已有的 engineering_observation。该字段会写入 retrieval_trace.context。"
        ),
    )
    topic_tags: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。topic tag 过滤条件。当前项目中该字段有用：非空时会写入 "
            "ResearchKnowledgeRecallQuery.topic_tags，Postgres store 会使用 topic_tags JSONB 字段进行过滤；"
            "空列表表示不按 topic tag 限制。它用于把语义召回限制在更相关的主题范围内，例如 postgresql、"
            "pgvector、retrieval。该字段会写入 retrieval_trace.context。"
        ),
    )
    source_types: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。knowledge unit 的 primary source_type 过滤条件。当前项目中该字段有用："
            "非空时会写入 ResearchKnowledgeRecallQuery.source_types，Postgres store 会用它过滤 "
            "ResearchKnowledgeUnitRecord.source_type。注意它不是 NormalizedRetrievalItem.source_references[*].source_type "
            "的完整集合过滤，而是 research_knowledge_units 表上记录的 primary source_type。空列表表示不限制。"
        ),
    )
    limit: int = Field(
        default=5,
        ge=1,
        description=(
            "可选字段，默认 5，必须大于等于 1。请求召回的 knowledge unit 数量上限。当前项目中该字段有用："
            "ResearchKnowledgeMemoryTool 会将它写入 ResearchKnowledgeRecallQuery.limit；"
            "PostgresResearchKnowledgeMemoryStore 会再结合自身 config.max_recall_limit 做上限保护。"
            "该字段影响最终 ResearchKnowledgeMemoryToolResult.normalized_items 的最大候选数量。"
        ),
    )
