"""web_search adapter 的单条标准化结果模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WebSearchResult(BaseModel):
    """open web search adapter 返回的一条标准化搜索结果。

    该模型不是最终 NormalizedRetrievalItem，也不包含网页正文抓取结果；
    它表示 search provider 返回并经过 adapter 归一化的一条 search result。
    当前项目中唯一生产方是 TavilyWebSearchClient，主要消费方是 TavilyWebSearchTool。
    TavilyWebSearchTool 会基于 score / rank / URL 选择是否继续调用 web_content_fetch，
    并最终把该对象转换为 NormalizedRetrievalItem。
    """

    item_id: str = Field(
        min_length=1,
        description=(
            "必填字段。当前 web search response 内的稳定 result 标识。当前项目中该字段有用："
            "TavilyWebSearchClient 当前使用 URL 的 sha1 生成 item_id；TavilyWebSearchTool 会把它透传为 "
            "NormalizedRetrievalItem.item_id，EvidenceProcessingService 后续会用 item_id 辅助去重和生成 evidence metadata。"
            "它只要求在当前 retrieval 输出内稳定，不要求跨 provider 全局唯一。"
        ),
    )
    title: str = Field(
        min_length=1,
        description=(
            "必填字段。search provider 返回的结果标题。当前项目中该字段有用："
            "TavilyWebSearchClient 从 Tavily item['title'] 归一化得到该字段；TavilyWebSearchTool 会将它写入 "
            "NormalizedRetrievalItem.metadata['title']，也会用于 SourceReference.title 和 citation_text。"
            "如果 provider item 缺少 title，当前 adapter 会丢弃该 item。"
        ),
    )
    snippet: str = Field(
        min_length=1,
        description=(
            "必填字段。search provider 返回的摘要片段。当前项目中该字段有用："
            "TavilyWebSearchClient 当前优先从 Tavily item['content'] 获取，若没有则尝试 item['snippet']；"
            "TavilyWebSearchTool 会把它写入 metadata['search_snippet']。当 web content fetch 未请求、失败或返回空内容时，"
            "snippet 会作为 NormalizedRetrievalItem.content 的 fallback。若 provider item 缺少可用 snippet，当前 adapter 会丢弃该 item。"
        ),
    )
    url: str = Field(
        min_length=1,
        description=(
            "必填字段。搜索结果指向的原始网页 URL。当前项目中该字段有用："
            "TavilyWebSearchClient 从 Tavily item['url'] 归一化得到该字段；TavilyWebSearchTool 会用它决定内容抓取候选、"
            "构造 WebContentFetchRequest.urls、关联 web_content_fetch 结果，并写入 SourceReference.source_url。"
            "如果 provider item 缺少 URL，当前 adapter 会丢弃该 item。"
        ),
    )
    source_name: str = Field(
        min_length=1,
        description=(
            "必填字段。底层 search provider 名称。当前项目中该字段有用："
            "TavilyWebSearchClient 当前固定写入 tavily；TavilyWebSearchTool 会将它写入 "
            "NormalizedRetrievalItem.metadata['search_source_name']，并放入 SourceReference.metadata['source_name']。"
            "该字段表示检索 provider，不等同于网页 publisher，也不应伪装成 SourceReference.publisher。"
        ),
    )
    published_at: datetime | None = Field(
        default=None,
        description=(
            "可选字段。provider 报告的网页发布时间或发布日期。当前项目中该字段有用但经常为空："
            "TavilyWebSearchClient 当前从 Tavily item['published_date'] 解析得到该字段；TavilyWebSearchTool 会将它写入 "
            "NormalizedRetrievalItem.metadata['published_at']，并映射到 SourceReference.published_at。"
            "它表示原始网页发布时间，不是系统检索时间，也不是 content fetch 时间。"
        ),
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "可选字段，默认 0.0，必须大于等于 0。adapter-local 的相关性分数。当前项目中该字段有用："
            "TavilyWebSearchClient 当前从 Tavily item['score'] 解析得到该字段；TavilyWebSearchTool 会用它和 "
            "TavilyWebSearchToolRequest.min_score_threshold 判断哪些 search results 有资格进入后续处理，"
            "并将它写入 NormalizedRetrievalItem.metadata['score']。该分数只在当前 provider / adapter 语境内有意义，"
            "不应和其它 provider 的分数直接比较。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。web search adapter 保留的 provider-specific 附加信息。当前项目中该字段有用，"
            "但它不是稳定主字段；调用方应优先使用 item_id、title、snippet、url、source_name、published_at、score。"
            "当前 TavilyWebSearchClient 会写入这些 key：rank，表示该结果在本次 provider response 中的 1-based 排序；"
            "favicon，可选，表示 provider 返回的网页 favicon URL。TavilyWebSearchTool 会把该 metadata 合并进 "
            "NormalizedRetrievalItem.metadata，并继续叠加 content_fetch_status、fallback_to_search_snippet、"
            "content_fetch_error_info、fetched_images、fetched_favicon 等 tool-level 信息。该字段不应承载完整 provider raw response、"
            "网页正文或大型 debug payload。"
        ),
    )
