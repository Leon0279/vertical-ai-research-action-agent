"""llms_txt_docs_search tool 的运行时输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LlmsTxtDocsSearchToolRequest(BaseModel):
    """docs_search family 调用 llms_txt_docs_search tool 时使用的标准化输入。

    该模型不是 docs_search adapter 的原始请求，而是 tool 层运行时请求。
    当前项目中它通常由 DocsSearchFamilyService 根据 family request 构造；
    未来新版 Research Executor 会通过 Tool Execution Layer 间接影响这些字段。
    """

    query_text: str = Field(
        min_length=1,
        description=(
            "必填字段。docs search tool 实际执行的检索 query。当前项目中该字段有用："
            "上游通常由 RetrievalQueryGenerationService 生成 query，再经 ToolExecutionLayerService "
            "和 DocsSearchFamilyService 映射到这里；LlmsTxtDocsSearchTool 会用它构造 "
            "DocsSearchQuery.query_text 并传给 docs_search adapter。"
        ),
    )
    target_problem: str | None = Field(
        default=None,
        description=(
            "可选字段。上层希望解决的目标问题或 retrieval intent。当前项目中该字段有用："
            "ToolExecutionLayerService 会从请求目标传入，DocsSearchFamilyService 继续透传；"
            "LlmsTxtDocsSearchTool 会把它写入 DocsSearchQuery.target_problem，并在 retrieval_trace "
            "中作为 target_problem 保留，供后续 TEL / EvidenceProcessing 理解检索语境。"
        ),
    )
    freshness_requirement: str | None = Field(
        default=None,
        description=(
            "可选字段。对 docs 检索结果新鲜度的提示，例如 fresh_required、fresh_preferred "
            "或其它上游约定值。当前项目中该字段有用：它可由 EvidenceShape.freshness_requirement "
            "或 ToolExecutionLayerRequest 约束派生，并透传到 DocsSearchQuery.freshness_requirement。"
            "当前 llms.txt docs adapter 会接收该字段作为检索意图信号；该字段不是 tool 自己计算出的状态。"
        ),
    )
    sub_source_types: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。限制 docs adapter 只搜索哪些 docs 子来源类型。当前项目中该字段有用："
            "DocsSearchFamilyRequest / ToolExecutionLayerRequest 可传入该约束，LlmsTxtDocsSearchTool "
            "会过滤空字符串后写入 DocsSearchQuery.sub_source_types。示例值包括 openai_api、"
            "anthropic_api、claude_code。空列表表示不按子来源类型限制，由 adapter 使用其全部已配置来源。"
        ),
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description=(
            "可选字段，默认 5，必须大于等于 1。限制 docs_search adapter 最多返回和保留多少条候选结果。"
            "当前项目中该字段有用：DocsSearchFamilyService 和 ToolExecutionLayerService 会把 max_search_results "
            "约束传到这里；LlmsTxtDocsSearchTool 会用它设置 DocsSearchQuery.limit，并间接影响 "
            "LlmsTxtDocsSearchToolResult.normalized_items 的最大数量。"
        ),
    )
