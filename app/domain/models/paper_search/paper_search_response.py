"""paper_search adapter 的分页响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.models.paper_search.paper_search_result import PaperSearchResult


class PaperSearchResponse(BaseModel):
    """paper_search adapter 返回的标准化分页响应。

    当前项目中该模型由 paper_search adapter 返回给 `ArxivPaperSearchTool`。它只承载论文 metadata
    search 结果和 provider 分页信息，不包含 PDF/full text 抓取内容；全文抓取由 `PaperContentFetchRequest`
    和 `PaperContentFetchResult` 表达。
    """

    results: list[PaperSearchResult] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前页的标准化论文 metadata 结果。当前项目中有用："
            "ArxivPaperSearchTool 会读取这些 `PaperSearchResult`，先生成摘要型 normalized item，再按 `max_content_fetches` "
            "选择部分候选调用 paper_content_fetch adapter。列表为空时，tool 会返回 `acquisition_status='no_result'`。"
        ),
    )
    total_results: int | None = Field(
        default=None,
        description=(
            "可选字段。provider 报告的匹配结果总数。当前项目中有用但使用较轻："
            "arXiv adapter 可从 provider 响应中填充它，用于分页/诊断；当前 ArxivPaperSearchTool 主要消费 `results`，"
            "不会基于该字段自动拉取后续页面。"
        ),
    )
    start_index: int | None = Field(
        default=None,
        description=(
            "可选字段。provider 报告的当前页起始 index。当前项目中有用但使用较轻："
            "主要用于保留 provider pagination provenance 和调试分页问题；当前 tool 不依赖它做业务分支。"
        ),
    )
    items_per_page: int | None = Field(
        default=None,
        description=(
            "可选字段。provider 报告的每页 item 数量或当前页返回数量。当前项目中有用但使用较轻："
            "主要用于诊断 provider 是否按 `PaperSearchQuery.limit` 返回结果；当前 tool 不依赖它判断 acquisition_status。"
        ),
    )
