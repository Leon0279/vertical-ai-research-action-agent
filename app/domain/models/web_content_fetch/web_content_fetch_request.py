"""Web content fetch adapter 的标准化输入模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WebContentFetchRequest(BaseModel):
    """用于网页正文抽取的 provider-neutral 请求模型。

    这个模型是 `WebContentFetchClientProtocol.fetch_content(...)` 的输入，
    当前主要由 `TavilyWebSearchTool` 在选出需要深度抓取的网页 URL 后创建，
    再交给 `TavilyWebContentFetchClient` 转换为 Tavily Extract 请求。

    它不是 web search 查询模型：web search 负责发现候选网页，web content fetch
    只负责对已知 URL 做正文抽取、可选图片/favicon 抽取和 provider usage 返回。
    """

    urls: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表；待抽取正文内容的绝对 HTTP(S) URL 列表。"
            "当前项目中有用：`TavilyWebSearchTool` 会把 web search 选中的候选网页 URL "
            "放入该字段，用于后续正文抓取。虽然模型层允许默认空列表，但 "
            "`TavilyWebContentFetchClient` 运行时会要求至少包含一个非空 HTTP(S) URL，"
            "否则会返回输入校验错误。"
        ),
    )
    query: str | None = Field(
        default=None,
        description=(
            "可选字段；面向 provider 的内容抽取聚焦 query，用于要求 provider 只返回与该 query "
            "更相关的正文片段。当前项目中暂未由 `TavilyWebSearchTool` 设置，"
            "通常为空；如果未来需要 query-based extraction，可由上游传入 retrieval query "
            "或子问题作为聚焦依据。"
        ),
    )
    chunks_per_source: int | None = Field(
        default=None,
        description=(
            "可选字段；query-based extraction 时每个 URL 希望返回的 chunk 数量。"
            "当前项目中暂未使用，通常为空；`TavilyWebContentFetchClient` 会要求该字段只有在 "
            "`query` 非空时才能使用，并限制在 provider 支持的范围内。"
        ),
    )
    extract_depth: Literal["basic", "advanced"] | None = Field(
        default=None,
        description=(
            "可选字段；provider 抽取深度覆盖值，可为 `basic` 或 `advanced`。"
            "当前项目中有用：如果调用方不传，`TavilyWebContentFetchClient` 会使用 adapter config "
            "中的默认抽取深度；如果传入，则用于控制 Tavily Extract 的正文抽取强度。"
        ),
    )
    include_images: bool | None = Field(
        default=None,
        description=(
            "可选字段；是否请求 provider 返回页面中的图片 URL。当前项目中有用但默认通常由 adapter "
            "config 决定；如果返回图片，成功结果会写入 `WebContentFetchResult.images`，"
            "随后 `TavilyWebSearchTool` 会把它们放入 normalized item 的 metadata "
            "`fetched_images` 中作为补充 provenance。"
        ),
    )
    include_favicon: bool | None = Field(
        default=None,
        description=(
            "可选字段；是否请求 provider 返回页面 favicon URL。当前项目中有用但默认通常由 adapter "
            "config 决定；如果返回 favicon，成功结果会写入 `WebContentFetchResult.favicon`，"
            "随后 `TavilyWebSearchTool` 会把它放入 normalized item 的 metadata "
            "`fetched_favicon` 中。"
        ),
    )
    format: Literal["markdown", "text"] | None = Field(
        default=None,
        description=(
            "可选字段；期望 provider 返回的正文格式，可为 `markdown` 或 `text`。"
            "当前项目中有用：`TavilyWebSearchTool` 当前会传 `markdown`，使正文更适合后续 evidence "
            "processing 保留标题、列表等轻结构；如果为空，adapter 会使用配置默认值。"
        ),
    )
    timeout_seconds: float | None = Field(
        default=None,
        description=(
            "可选字段；provider-side 页面抽取超时时间，单位秒。当前项目中有用：调用方可用它控制 "
            "单次 Tavily Extract 请求的等待预算；如果为空，adapter 会使用配置默认超时时间。"
            "`TavilyWebContentFetchClient` 会校验该值必须位于 provider 支持范围内。"
        ),
    )
    include_usage: bool | None = Field(
        default=None,
        description=(
            "可选字段；是否请求 provider 返回 usage / billing / credits 等用量信息。"
            "当前项目中有用但通常由 adapter config 决定；若 provider 返回 usage，"
            "会进入 `WebContentFetchResponse.usage`，主要用于调试、成本观测或未来运行时计量，"
            "当前 `TavilyWebSearchTool` 不依赖该字段做业务判断。"
        ),
    )
