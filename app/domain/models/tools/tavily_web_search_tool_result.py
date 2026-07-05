"""Tavily web search tool 的标准化输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import AcquisitionStatus
from app.domain.models.retrieval import (
    NormalizedRetrievalItem,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)


class TavilyWebSearchToolResult(BaseModel):
    """`TavilyWebSearchTool.run(...)` 返回的标准化 tool 执行结果。

    该结果会被 `WebSearchFamilyService` 包装成 family result，再继续传给
    Tool Execution Layer、Request Completion Evaluation 和 Evidence Processing。
    它表示一次 web_search tool 执行产出的候选材料，而不是最终结论；正文可能来自 Tavily
    content fetch，也可能在抓取失败或未抓取时回退为 web search snippet。
    """

    normalized_items: list[NormalizedRetrievalItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表；跨 tools/families/TEL/EvidenceProcessing 传递的候选材料主数据。"
            "当前项目中有用：web_search family 会原样透传这些 item，EvidenceProcessing 会进一步去重、"
            "结构化和归纳。每个 item 当前包含 `source_family='web_search'`、"
            "`source_references`（通常长度为 1，指向原始 web page）、`content`、`content_type` "
            "和 metadata。metadata 当前可能包含："
            "`title`（网页标题）、`rank`（搜索结果排名，从 1 开始）、`score`（搜索分数）、"
            "`search_snippet`（原始搜索摘要）、`search_source_name`（搜索 adapter/source 名称）、"
            "`published_at`（搜索结果发布时间，ISO 字符串或 None）、"
            "`content_fetch_status`（`succeeded` / `empty_content` / `failed` / `not_requested`）、"
            "`content_fetch_source`（正文抓取 provider，例如 `tavily_extract`）、"
            "`fetched_images`、`fetched_favicon`、`fallback_to_search_snippet`、"
            "`content_fetch_error_info`，以及 web search result / content fetch result 自带的 "
            "provider-specific metadata。"
        ),
    )
    acquisition_status: AcquisitionStatus = Field(
        description=(
            "必填字段；本次 tool acquisition 的整体状态。当前项目中有用：family service、TEL 和 "
            "RequestCompletionEvaluationService 会依赖它判断本轮 retrieval 是否完成、是否需要恢复。"
            "取值含义：`success` 表示至少有正文抓取成功且没有 empty/failed 抓取；"
            "`partial_success` 表示有候选材料但存在正文抓取为空、失败、禁用或其它降级；"
            "`no_result` 表示 web search 没有返回候选；`failed` 表示 web search adapter 调用失败。"
        ),
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0；tool 层标准化过程中被丢弃的 item 数量。当前项目中有用，"
            "但 `TavilyWebSearchTool` 当前没有额外丢弃 search candidate 的逻辑，因此通常为 0；"
            "family/TEL/evidence processing 会把它作为降级和统计信息继续传递。"
        ),
    )
    source_summary: RetrievalSourceSummary = Field(
        default_factory=RetrievalSourceSummary,
        description=(
            "可选字段，默认空 `RetrievalSourceSummary`；本 tool 输出的来源摘要。当前项目中有用："
            "`TavilyWebSearchTool` 当前主要设置 `normalized_count`，表示返回的 normalized item 数量；"
            "`selected_family` / `selected_tool` 通常由上游 `WebSearchFamilyService` 在包装 family result "
            "时设置，而不是由底层 content fetch adapter 设置。该对象的 `metadata` 可承载来源覆盖或 "
            "provider-specific 摘要，但当前本 tool 不额外写入 metadata。"
        ),
    )
    execution_summary: RetrievalExecutionSummary = Field(
        default_factory=RetrievalExecutionSummary,
        description=(
            "可选字段，默认空 `RetrievalExecutionSummary`；本 tool 执行层面的计数与降级观测信息。"
            "当前项目中有用：TEL、family result 和测试都会读取其中的统计。"
            "`TavilyWebSearchTool` 当前会设置正式字段 `normalized_count`、`dropped_item_count`，"
            "并在 `metrics` dict 中写入："
            "`search_result_count`（参与组装的 web search candidate 数）、"
            "`selected_for_fetch_count`（被选中做正文抓取的 URL 数）、"
            "`fetch_success_count`（正文抓取成功数）、"
            "`fetch_empty_count`（provider 返回结果但正文为空的数量）、"
            "`fetch_failed_count`（provider 失败、批量抓取异常或缺少匹配结果的数量）。"
            "`observability` 当前不由本 tool 写入，保留给更细的调试信息。"
        ),
    )
    retrieval_trace: RetrievalTrace = Field(
        default_factory=RetrievalTrace,
        description=(
            "可选字段，默认空 `RetrievalTrace`；本 tool 的轻量 retrieval trace。当前项目中有用："
            "用于观察 web search candidate 和 content fetch 的路径，不是完整 tracing framework。"
            "失败路径会在 `errors` dict 中写入 `search_error`，表示 web search adapter 调用失败。"
            "正常/降级路径会在 `observability` dict 中写入："
            "`attempted_urls`（参与组装的搜索结果 URL 列表）、"
            "`selected_for_fetch`（被送入 content fetch 的 URL 列表）、"
            "`fetched_urls`（content fetch 返回 succeeded 或 empty_content 结果的 URL 列表）、"
            "`failed_fetches`（正文抓取失败列表，每项当前为 `{'url': ..., 'error_info': ...}`）。"
            "上游 family service 会在包装时补充 `selected_family`、`selected_tool` 等 provenance。"
        ),
    )
    error_info: str | None = Field(
        default=None,
        description=(
            "可选字段；顶层失败摘要。当前项目中有用：当 `acquisition_status='failed'` 时，"
            "`TavilyWebSearchTool` 会写入 web search adapter 抛出的简短错误信息；"
            "当 acquisition 为 `success`、`partial_success` 或 `no_result` 时通常为 None。"
            "正文抓取的单 URL 失败不会放在这里，而是进入 item metadata 的 "
            "`content_fetch_error_info` 和 `retrieval_trace.observability['failed_fetches']`。"
        ),
    )
