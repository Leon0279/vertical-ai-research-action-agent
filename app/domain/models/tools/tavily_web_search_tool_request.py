"""Tavily web search tool 的运行时输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TavilyWebSearchToolRequest(BaseModel):
    """`TavilyWebSearchTool.run(...)` 的标准化运行时输入。

    这个模型位于 tool service 边界，由 web_search family / Tool Execution Layer
    根据已生成的 retrieval query 和执行约束映射而来。它不是 Tavily adapter 的原始请求：
    tool 会先把其中的搜索字段转换成 `WebSearchQuery` 调用 web search adapter，
    再根据 `max_content_fetches` / `min_score_threshold` 选择部分搜索结果调用
    web content fetch adapter 抽取正文。
    """

    query_text: str = Field(
        min_length=1,
        description=(
            "必填字段；要交给 web search adapter 执行的搜索 query。当前项目中有用："
            "通常由 Retrieval Query Generation Service 生成，并经 web_search family 透传到本 tool。"
            "`TavilyWebSearchTool` 会 trim 该字段后写入 `WebSearchQuery.query_text`，"
            "它直接决定搜索召回的网页候选范围。"
        ),
    )
    target_problem: str | None = Field(
        default=None,
        description=(
            "可选字段；上游任务或本轮 retrieval 的目标问题，用于保留 query 背后的高层意图。"
            "当前项目中有用：tool 会 trim 后透传给 `WebSearchQuery.target_problem`，"
            "adapter / 后续 trace 可用它理解搜索语境；即使当前 Tavily adapter 不一定直接使用，"
            "它仍是跨 TEL/family/tool 链路的上下文信息。"
        ),
    )
    freshness_requirement: str | None = Field(
        default=None,
        description=(
            "可选字段；对信息新鲜度的要求或提示，例如 latest、recent、fresh_required 等上游语义。"
            "当前项目中有用：通常来自 `EvidenceShape.freshness_requirement` 或 TEL request 约束，"
            "tool 会 trim 后透传给 `WebSearchQuery.freshness_requirement`，供 web search adapter "
            "决定是否偏向近期公开网页。"
        ),
    )
    include_domains: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表；允许或优先纳入搜索的 domain 列表。当前项目中有用："
            "tool 会过滤空字符串后透传给 `WebSearchQuery.include_domains`，用于限制或引导 "
            "Tavily web search 的来源范围。列表元素应是 domain 字符串，不应包含 URL path。"
        ),
    )
    exclude_domains: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表；需要从搜索中排除的 domain 列表。当前项目中有用："
            "tool 会过滤空字符串后透传给 `WebSearchQuery.exclude_domains`，用于排除低质量、"
            "不允许或与本轮任务无关的来源。列表元素应是 domain 字符串，不应包含 URL path。"
        ),
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description=(
            "可选字段，有默认值 5，最小值 1；本 tool 最多保留多少条 web search candidate "
            "用于组装最终 normalized items。当前项目中有用：该字段会传给 `WebSearchQuery.limit`，"
            "同时在 search response 返回后再次截断 `search_response.results`，决定最终候选材料上限。"
        ),
    )
    max_content_fetches: int = Field(
        default=3,
        ge=0,
        description=(
            "可选字段，有默认值 3，最小值 0；最多选择多少个搜索结果 URL 进入 web content fetch "
            "正文抽取。当前项目中有用：大于 0 时，tool 会优先选择 score 达到 "
            "`min_score_threshold` 的候选，再按顺序补足；等于 0 时禁用正文抓取，所有 item "
            "只使用 web search snippet，metadata 中的 `content_fetch_status` 为 `not_requested`。"
        ),
    )
    min_score_threshold: float = Field(
        default=0.5,
        ge=0.0,
        description=(
            "可选字段，有默认值 0.5，最小值 0.0；选择正文抓取候选时使用的最低搜索分数阈值。"
            "当前项目中有用：tool 会先选择 `WebSearchResult.score >= min_score_threshold` 的结果，"
            "如果数量不足 `max_content_fetches`，再按搜索结果顺序补齐。该字段只影响哪些 URL "
            "会进入 content fetch，不影响 web search adapter 的搜索召回。"
        ),
    )
