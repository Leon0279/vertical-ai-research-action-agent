"""Web content fetch adapter 的标准化结果模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

WebContentFetchStatus = Literal["succeeded", "empty_content"]


class WebContentFetchResult(BaseModel):
    """单个 URL 的成功或降级正文抽取结果。

    当前由 `TavilyWebContentFetchClient` 从 Tavily Extract 的 `results` item 标准化得到。
    这里的“成功或降级”指 provider 至少返回了该 URL 的结果对象：如果有正文内容，
    `fetch_status` 为 `succeeded`；如果 URL 被返回但正文为空，则 `fetch_status` 为
    `empty_content`，上游 tool 会回退使用 web search snippet。
    """

    item_id: str = Field(
        min_length=1,
        description=(
            "必填字段；该 fetch result 的稳定 ID。当前 `TavilyWebContentFetchClient` 使用 URL 的 "
            "SHA1 生成，用于在 adapter 结果内部稳定标识该 URL。当前项目中有用但不是最终 provenance "
            "主字段：上游 `TavilyWebSearchTool` 主要通过 `url` 把 fetch result 与 web search "
            "candidate 关联。"
        ),
    )
    url: str = Field(
        min_length=1,
        description=(
            "必填字段；本次正文抽取对应的原始网页 URL。当前项目中有用：`TavilyWebSearchTool` 会用该字段"
            "把 content fetch 结果匹配回 `WebSearchResult.url`，并在构造 `SourceReference` 时继续"
            "使用 web search candidate 的 URL 作为原始网页来源。"
        ),
    )
    extracted_content: str | None = Field(
        default=None,
        description=(
            "可选字段；provider 抽取并经 adapter 轻量标准化后的网页正文内容。当前项目中有用：当 "
            "`fetch_status='succeeded'` 且该字段非空时，`TavilyWebSearchTool` 会把它作为 "
            "`NormalizedRetrievalItem.content`，并把 content type 设置为 `document_chunk`。"
            "如果正文为空，该字段为 None，上游会回退使用搜索摘要。"
        ),
    )
    fetch_status: WebContentFetchStatus = Field(
        description=(
            "必填字段；该 URL 的正文抽取状态。当前允许值：`succeeded` 表示成功获得正文，"
            "`empty_content` 表示 provider 返回了该 URL 的结果但正文为空。当前项目中有用："
            "`TavilyWebSearchTool` 依赖该字段决定是使用抓取正文，还是降级回 web search snippet，"
            "并据此统计 `fetch_success_count` / `fetch_empty_count`。"
        ),
    )
    images: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表；provider 抽取到的页面图片 URL。当前项目中有用但属于补充 provenance："
            "如果存在，`TavilyWebSearchTool` 会写入 normalized item metadata 的 `fetched_images`，"
            "供后续调试、展示或未来 richer evidence UI 使用；当前 evidence processing 不依赖图片做判断。"
        ),
    )
    favicon: str | None = Field(
        default=None,
        description=(
            "可选字段；provider 返回的网页 favicon URL。当前项目中有用但属于补充 provenance："
            "`TavilyWebSearchTool` 会写入 normalized item metadata 的 `fetched_favicon`，"
            "当前不参与 retrieval completion 或 evidence processing 的核心判断。"
        ),
    )
    error_info: str | None = Field(
        default=None,
        description=(
            "可选字段；成功结果对象中的降级说明。当前主要在 `fetch_status='empty_content'` 时由 adapter "
            "写入，例如 `Content extraction produced no content.`。当前项目中有用："
            "`TavilyWebSearchTool` 会把它放入 normalized item metadata 的 "
            "`content_fetch_error_info`，帮助解释为什么回退到搜索摘要。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict；单条成功/降级结果的 provider-specific 附加信息。"
            "`TavilyWebContentFetchClient` 当前会把 provider result item 中除 `url`、`raw_content`、"
            "`images`、`favicon` 以外的字段放入这里。当前测试和 provider payload 中可能包含 "
            "`title` 等页面元信息；未来也可能包含 provider score、解析模式、内容长度、站点 metadata 等。"
            "当前项目中有用：`TavilyWebSearchTool` 会把该 dict merge 到 normalized item metadata，"
            "但这些 key 不应被视为跨 provider 稳定 contract。"
        ),
    )
    source: str = Field(
        default="tavily_extract",
        description=(
            "可选字段，有默认值；content fetch provider 名称。当前默认为 `tavily_extract`。"
            "当前项目中有用：`TavilyWebSearchTool` 会写入 normalized item metadata 的 "
            "`content_fetch_source`，用于区分正文内容来自搜索摘要还是来自 Tavily Extract 抽取。"
        ),
    )


class WebContentFetchFailedResult(BaseModel):
    """单个 URL 的正文抽取失败结果。

    当前由 `TavilyWebContentFetchClient` 从 Tavily Extract 的 `failed_results` item 标准化得到。
    它表示 provider 明确告诉我们某个 URL 抽取失败，而不是“返回成功结果但正文为空”。
    上游 tool 会使用它记录失败原因，并回退到 web search snippet。
    """

    url: str = Field(
        min_length=1,
        description=(
            "必填字段；正文抽取失败的原始 URL。当前项目中有用：`TavilyWebSearchTool` 会用它把失败结果"
            "匹配回 `WebSearchResult.url`，并在 trace 的 `failed_fetches` 中记录该 URL。"
            "如果 provider 的失败 item 没有给 URL，adapter 当前会使用 `unknown` 作为保守兜底。"
        ),
    )
    error_info: str = Field(
        min_length=1,
        description=(
            "必填字段；provider 或 adapter 层给出的简短失败原因。当前项目中有用："
            "`TavilyWebSearchTool` 会写入 normalized item metadata 的 `content_fetch_error_info`，"
            "并进入 trace 的 `failed_fetches`，用于解释为什么该 candidate 只能回退到搜索摘要。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict；失败结果的 provider-specific 附加信息。"
            "`TavilyWebContentFetchClient` 当前会把失败 item 中除 `url`、`error`、`reason`、`message` "
            "以外的字段放入这里。当前测试中包含 `status_code`；未来可能包含 provider error code、"
            "retry-after、crawl block reason、raw status 等。当前项目中有用：`TavilyWebSearchTool` "
            "会把这些字段 merge 到 normalized item metadata，用于调试和 provenance；这些 key "
            "不是跨 provider 稳定业务字段。"
        ),
    )
