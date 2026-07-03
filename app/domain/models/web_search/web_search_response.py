"""web_search adapter 的标准化输出容器模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.web_search.web_search_result import WebSearchResult


class WebSearchResponse(BaseModel):
    """open web search adapter 返回的标准化结果容器。

    该模型承载 provider-neutral 的 web search results 和 adapter-level source summary。
    当前项目中唯一实现是 TavilyWebSearchClient；它会被 TavilyWebSearchTool 消费，再转换为
    TavilyWebSearchToolResult。该模型不是 ToolExecutionLayerResult，也不包含 content fetch 结果；
    网页正文抓取由 TavilyWebSearchTool 后续调用 web_content_fetch adapter 完成。
    """

    results: list[WebSearchResult] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。adapter 归一化后的 web search result 列表。当前项目中该字段有用："
            "TavilyWebSearchTool 会读取每个 WebSearchResult，按 score 和 min_score_threshold 选择候选，"
            "再决定是否调用 web_content_fetch 获取正文。每个 WebSearchResult 当前包含 item_id、title、snippet、url、"
            "source_name、published_at、score、metadata。空列表表示 provider 没有返回可归一化的搜索结果。"
        ),
    )
    source_summary: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。web_search adapter-level 的来源摘要与轻量统计。当前项目中该字段有用，"
            "但它仍是 adapter response 内的裸 dict，不是跨层 retrieval summary；TavilyWebSearchTool 会读取其中的部分信息，"
            "并在 tool result 中重新构造 typed RetrievalSourceSummary。当前 TavilyWebSearchClient 会写入这些 key："
            "provider='tavily'，表示底层搜索 provider；query_text，表示规范化后的 WebSearchQuery.query_text；"
            "normalized_count，表示成功归一化进入 results 的数量；dropped_item_count，表示 provider 返回但无法归一化的 item 数量。"
            "selected_family 和 selected_tool 不应由 adapter 设置；它们属于 tool/family execution provenance，"
            "应由 TavilyWebSearchTool / WebSearchFamilyService 在上游 typed result 中设置。"
            "该 dict 不应承载完整 provider raw response、大型 debug payload 或网页正文。"
        ),
    )
