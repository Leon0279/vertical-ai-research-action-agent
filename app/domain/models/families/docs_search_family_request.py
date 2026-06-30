"""docs_search family service 的运行时输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocsSearchFamilyRequest(BaseModel):
    """DocsSearchFamilyService.run(...) 使用的 family 层标准化请求。

    该模型不是 llms_txt_docs_search tool 的请求，也不是 docs_search adapter 的原始请求；
    它位于 Tool Execution Layer 和具体 docs tool 之间。当前项目中通常由
    ToolExecutionLayerService 根据 selected_family、generated_query 和上游约束构造，
    DocsSearchFamilyService 会负责选择 family 内部 tool，并把字段映射到 LlmsTxtDocsSearchToolRequest。
    """

    query_text: str = Field(
        min_length=1,
        description=(
            "必填字段。docs_search family 本次要执行的检索 query。当前项目中该字段有用："
            "通常由 RetrievalQueryGenerationService 在 TEL 内生成，再由 ToolExecutionLayerService "
            "写入 DocsSearchFamilyRequest；DocsSearchFamilyService 会去除首尾空白后透传给 "
            "LlmsTxtDocsSearchToolRequest.query_text，最终进入 DocsSearchQuery.query_text。"
        ),
    )
    target_problem: str | None = Field(
        default=None,
        description=(
            "可选字段。上层 request 想解决的目标问题或 retrieval intent。当前项目中该字段有用："
            "ToolExecutionLayerService 会从 ToolExecutionLayerRequest.target_problem 映射到这里；"
            "DocsSearchFamilyService 会透传给 LlmsTxtDocsSearchToolRequest.target_problem，后续 tool/adapter/trace "
            "会保留它，EvidenceProcessingService 可通过 retrieval_trace 理解 evidence structuring 的目标语境。"
        ),
    )
    freshness_requirement: str | None = Field(
        default=None,
        description=(
            "可选字段。对 docs 检索新鲜度的上游提示。当前项目中该字段有用："
            "通常由 EvidenceShape.freshness_requirement 或 ToolExecutionLayerRequest 中的 retrieval 约束派生；"
            "DocsSearchFamilyService 会透传给 LlmsTxtDocsSearchToolRequest.freshness_requirement，再进入 DocsSearchQuery。"
            "该字段是请求约束或意图，不是 docs family 自己判断出的 freshness 状态。"
        ),
    )
    sub_source_types: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。限制 docs_search family 只在指定 docs 子来源类型内检索。当前项目中该字段有用："
            "ToolExecutionLayerRequest.source_names 当前会映射到 docs family 的 sub_source_types；"
            "DocsSearchFamilyService 会过滤空字符串后透传给 LlmsTxtDocsSearchToolRequest.sub_source_types。"
            "示例值包括 openai_api、anthropic_api、claude_code。空列表表示不限制子来源，由 docs adapter 搜索所有已配置子来源。"
        ),
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description=(
            "可选字段，默认 5，必须大于等于 1。限制 docs_search family 本次最多保留多少条 docs search 结果。"
            "当前项目中该字段有用：ToolExecutionLayerService 会从 ToolExecutionLayerRequest.max_search_results 映射到这里；"
            "DocsSearchFamilyService 会透传给 LlmsTxtDocsSearchToolRequest.max_search_results，最终影响 docs adapter limit "
            "和返回的 normalized_items 数量。"
        ),
    )
    preferred_tool: str | None = Field(
        default=None,
        description=(
            "可选字段。上游指定的 docs_search family 内 preferred tool id。当前项目中该字段有用："
            "它只能由 Research Executor / ToolExecutionLayerService 作为 hint 原样传入；DocsSearchFamilyService 只用它和 "
            "family 内部 tool registry 做匹配。若为空，则选择默认 llms_txt_docs_search_v1；若非空但 registry 中不存在，"
            "family 返回 failed。family 不会根据上一次 selected_tool 自行合成、覆盖或推断 preferred_tool。"
        ),
    )
