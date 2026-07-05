"""web_search family service 的运行时输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WebSearchFamilyRequest(BaseModel):
    """`WebSearchFamilyService.run(...)` 的 family 层标准化输入。

    该模型由 Tool Execution Layer 根据 selected family、generated query 和执行约束映射而来，
    不是 Tavily web search adapter 的原始请求，也不是 `TavilyWebSearchTool` 的直接 public API。
    family service 会先根据 `preferred_tool` 和内部 tool registry 选择具体 tool，
    再把这些字段映射为 `TavilyWebSearchToolRequest`。具体 web search、content fetch、item
    normalization 仍由 tool 内部负责，family 层不直接调用 adapter。
    """

    query_text: str = Field(
        min_length=1,
        description=(
            "必填字段；web_search family 本次要执行的 retrieval query。当前项目中有用："
            "通常来自 Tool Execution Layer 的 RetrievalQueryGenerationService 输出，"
            "`WebSearchFamilyService` 会 trim 后透传给 `TavilyWebSearchToolRequest.query_text`。"
            "该字段决定 web search adapter 搜索公开网页的核心语义。"
        ),
    )
    target_problem: str | None = Field(
        default=None,
        description=(
            "可选字段；上游任务或本轮 retrieval 的目标问题，用来保留 query 背后的高层意图。"
            "当前项目中有用：family 会 trim 后透传给 tool，tool 再写入 `WebSearchQuery.target_problem`；"
            "后续 retrieval trace / EvidenceProcessing 可将它作为 evidence structuring 的上下文。"
        ),
    )
    freshness_requirement: str | None = Field(
        default=None,
        description=(
            "可选字段；本轮 retrieval 对信息新鲜度的要求或提示。当前项目中有用："
            "通常由 Tool Execution Layer 从 `EvidenceShape.freshness_requirement` 派生，"
            "family 会 trim 后透传给 tool，再进入 `WebSearchQuery.freshness_requirement`。"
            "web_search family 常用于 open web / current / latest 类问题，因此该字段对 web search 尤其重要。"
        ),
    )
    include_domains: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表；允许、优先或限制搜索的 domain 列表。当前项目中有用："
            "family 会过滤空字符串后透传给 `TavilyWebSearchToolRequest.include_domains`，再由 tool "
            "传给 `WebSearchQuery.include_domains`。元素应是 domain 字符串，例如 `openai.com`，"
            "不建议放完整 URL path。空列表表示不对 included domain 做额外约束。"
        ),
    )
    exclude_domains: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表；需要从 web search 中排除的 domain 列表。当前项目中有用："
            "family 会过滤空字符串后透传给 `TavilyWebSearchToolRequest.exclude_domains`，再由 tool "
            "传给 `WebSearchQuery.exclude_domains`。适合排除低质量来源、已知无关站点或策略上不允许的 domain。"
        ),
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description=(
            "可选字段，默认 5，最小值 1；本次 web_search family 最多保留多少条 web search 结果参与 "
            "tool 输出组装。当前项目中有用：family 会原样透传给 `TavilyWebSearchToolRequest.max_search_results`；"
            "tool 会同时用它设置 `WebSearchQuery.limit` 并截断返回候选。"
        ),
    )
    max_content_fetches: int = Field(
        default=3,
        ge=0,
        description=(
            "可选字段，默认 3，最小值 0；本次最多选择多少个 web search candidate URL 进入 web content fetch "
            "正文抽取。当前项目中有用：family 会原样透传给 tool；tool 会优先选择分数达到 "
            "`min_score_threshold` 的候选，不足时按搜索结果顺序补齐。值为 0 表示禁用正文抓取，"
            "最终 item 将只使用 web search snippet。"
        ),
    )
    min_score_threshold: float = Field(
        default=0.5,
        ge=0.0,
        description=(
            "可选字段，默认 0.5，最小值 0.0；选择 content fetch 候选时使用的搜索分数阈值。"
            "当前项目中有用：family 会原样透传给 tool；tool 先选择 `WebSearchResult.score >= min_score_threshold` "
            "的结果进入正文抓取候选，再按顺序补足 `max_content_fetches`。该字段不影响 web search adapter "
            "召回本身，只影响哪些搜索结果会被进一步抓正文。"
        ),
    )
    preferred_tool: str | None = Field(
        default=None,
        description=(
            "可选字段；Research Executor / Tool Execution Layer 传入的 family 内部 tool hint。"
            "当前项目中有用：`WebSearchFamilyService` 只用它在 family registry 中匹配可用 tool，"
            "不会自行推断、合成或覆盖该值。当前默认可用 tool id 是 `tavily_web_search_v1`。"
            "如果传入的 preferred tool 不在 registry 中，family 会返回 failed result，并且不会调用 tool。"
        ),
    )
