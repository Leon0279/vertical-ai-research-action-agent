"""Web content fetch adapter 的标准化响应容器。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.web_content_fetch.web_content_fetch_result import (
    WebContentFetchFailedResult,
    WebContentFetchResult,
)


class WebContentFetchResponse(BaseModel):
    """网页正文抽取 adapter 返回的标准化响应。

    当前由 `TavilyWebContentFetchClient` 创建，承载 Tavily Extract 对一批 URL 的抽取结果。
    它位于 adapter 边界，不是 tool/family/TEL 的最终 retrieval result；上游
    `TavilyWebSearchTool` 会读取其中的成功/失败结果，并把它们合并到
    `NormalizedRetrievalItem.metadata`、`RetrievalExecutionSummary` 和 `RetrievalTrace`
    中。
    """

    results: list[WebContentFetchResult] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表；provider 返回并被 adapter 成功标准化的网页正文抽取结果。"
            "当前项目中有用：`TavilyWebSearchTool` 会按 `url` 将这些结果与 web search candidate "
            "关联；`fetch_status='succeeded'` 时使用 `extracted_content` 替换搜索摘要，"
            "`fetch_status='empty_content'` 时回退使用搜索摘要并记录降级信息。"
        ),
    )
    failed_results: list[WebContentFetchFailedResult] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表；provider 明确返回的 URL 抽取失败结果。当前项目中有用："
            "`TavilyWebSearchTool` 会按 `url` 将失败原因写入 normalized item metadata "
            "`content_fetch_status='failed'`、`content_fetch_error_info`，并在 trace 的 "
            "`failed_fetches` 中保留简短失败信息。"
        ),
    )
    response_time: float | None = Field(
        default=None,
        description=(
            "可选字段；provider 返回的本次抽取请求耗时，单位秒。当前项目中有用但暂无核心业务消费方；"
            "主要用于 adapter 调试、性能观测或未来成本/延迟分析。若 provider 未返回或无法解析则为空。"
        ),
    )
    request_id: str | None = Field(
        default=None,
        description=(
            "可选字段；provider 返回的请求 ID。当前项目中有用但暂无核心业务消费方；"
            "主要用于排查 provider 调用问题、日志关联和外部支持定位。若 provider 未返回则为空。"
        ),
    )
    usage: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict；provider usage / billing / credits 等用量信息。"
            "当前 `TavilyWebContentFetchClient` 会原样接收 provider payload 中的 `usage` dict。"
            "当前可能包含的 key 取决于 provider，例如 `credits_used` 等；这些 key 不作为当前项目的稳定"
            "业务 contract。当前项目中有用但主要服务成本观测和调试，`TavilyWebSearchTool` 不依赖它"
            "决定 retrieval 行为。"
        ),
    )
    source_summary: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict；adapter-level 摘要信息，用于说明本次 content fetch 的 provider "
            "和标准化计数。当前 `TavilyWebContentFetchClient` 会填入："
            "`provider`（当前为 `tavily_extract`，表示底层 content fetch provider）、"
            "`normalized_count`（成功标准化进入 `results` 的数量）、"
            "`failed_count`（进入 `failed_results` 的数量）。"
            "`selected_family` / `selected_tool` 不属于 adapter-level 摘要，应该由上游 tool/family "
            "result 表达，不应由 `TavilyWebContentFetchClient` 写入。"
            "该字段当前仍是 dict，因为 web content fetch adapter 的 summary 尚未收敛为 shared retrieval "
            "typed model；稳定业务主数据应优先读取 `results` / `failed_results`。"
        ),
    )
