"""web_search adapter 的标准化输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WebSearchQuery(BaseModel):
    """open web search adapter 使用的 provider-neutral 检索请求。

    该模型不是 Tavily 的原始 HTTP payload，而是项目内部传给 web_search adapter 的标准化输入。
    当前项目中它通常由 TavilyWebSearchTool 根据 TavilyWebSearchToolRequest 构造；
    ToolExecutionLayerService / WebSearchFamilyService 会间接影响这些字段。TavilyWebSearchClient
    会把它转换成 Tavily search API payload。
    """

    query_text: str = Field(
        min_length=1,
        description=(
            "必填字段。当前 open web search 实际执行的检索 query。当前项目中该字段有用："
            "通常由 RetrievalQueryGenerationService 在 TEL 内生成，再经 WebSearchFamilyService / "
            "TavilyWebSearchTool 映射到这里；TavilyWebSearchClient 会去除首尾空白，并把它写入 Tavily payload['query']。"
            "如果 target_problem 非空，adapter 会把 target_problem 追加到 query 文本中，帮助 provider 理解检索目标。"
        ),
    )
    target_problem: str | None = Field(
        default=None,
        description=(
            "可选字段。上层 request 想解决的目标问题或 retrieval intent。当前项目中该字段有用："
            "TavilyWebSearchClient 会将它和 query_text 组合成更有上下文的 provider query，格式当前为 "
            "'<query_text>\\n\\nTarget problem: <target_problem>'；它不是单独传给 Tavily 的结构化字段。"
            "该字段帮助 web search 保持搜索范围贴近当前任务，但不代表最终 evidence conclusion。"
        ),
    )
    limit: int = Field(
        default=5,
        description=(
            "可选字段，默认 5。请求 web search adapter 最多返回多少条 search result。当前项目中该字段有用："
            "TavilyWebSearchClient 会校验它必须大于 0 且不能超过 TavilyWebSearchClientConfig.max_limit，"
            "然后写入 Tavily payload['max_results']。该字段影响 WebSearchResponse.results 的最大数量，"
            "也会间接影响 TavilyWebSearchTool 后续可 fetch content 的候选范围。"
        ),
    )
    freshness_requirement: str | None = Field(
        default=None,
        description=(
            "可选字段。对 open web search 新鲜度的上游提示。当前项目中该字段有用："
            "TavilyWebSearchClient 会把部分约定值映射成 Tavily time_range，例如 latest/today -> d，"
            "recent/this_week -> w，fresh/current/this_month -> m，this_year -> y。"
            "未识别或为空时不设置 time_range。该字段是请求约束或意图，不是 adapter 判断出的 freshness 状态。"
        ),
    )
    include_domains: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。允许或限制搜索结果来源域名的 allow-list。当前项目中该字段有用："
            "TavilyWebSearchClient 会过滤空字符串后，在非空时写入 Tavily payload['include_domains']。"
            "示例值包括 platform.openai.com、developers.openai.com。空列表表示不按 include domain 限制。"
        ),
    )
    exclude_domains: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。需要从搜索结果中排除的域名 block-list。当前项目中该字段有用："
            "TavilyWebSearchClient 会过滤空字符串后，在非空时写入 Tavily payload['exclude_domains']。"
            "示例值包括 reddit.com、example.com。空列表表示不排除特定域名。"
        ),
    )
