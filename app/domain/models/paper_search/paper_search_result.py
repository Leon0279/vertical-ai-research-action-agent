"""paper_search adapter 返回的单条标准化论文 metadata 模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PaperSearchResult(BaseModel):
    """外部 paper search adapter 返回的单条标准化论文 metadata。

    当前项目中该模型由 arXiv paper_search adapter 填充，并由 `ArxivPaperSearchTool` 消费。
    它描述论文 metadata 和可选下载定位信息，不包含全文正文；全文正文由 `PaperContentFetchResult.extracted_text`
    表达。tool 层会用这些字段构造 `SourceReference`、`NormalizedRetrievalItem.metadata` 和 content fetch request。
    """

    paper_id: str = Field(
        min_length=1,
        description=(
            "必填字段。当前 provider/adapter 语境下的稳定 paper result 标识，不能为空字符串。"
            "当前项目中有用：arXiv adapter 通常可用 arXiv ID 或 provider item id 填充；ArxivPaperSearchTool 会把它作为 "
            "`NormalizedRetrievalItem.item_id`，也会放入 item metadata，并在 content fetch request 中作为 `paper_id` 透传。"
        ),
    )
    title: str = Field(
        min_length=1,
        description=(
            "必填字段。论文标题，不能为空字符串。当前项目中有用：tool 会把它写入 `SourceReference.title`、"
            "`SourceReference.citation_text` 和 normalized item metadata；后续 evidence processing 可用它作为 citation/provenance 线索。"
        ),
    )
    authors: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。论文作者列表，尽量保持 provider 返回的顺序。当前项目中有用："
            "ArxivPaperSearchTool 会把它写入 `SourceReference.authors` 和 normalized item metadata。若 provider 未提供作者，"
            "保持空列表，不要用 provider 名称或 publisher 伪造作者。"
        ),
    )
    summary: str | None = Field(
        default=None,
        description=(
            "可选字段。论文摘要或 provider 返回的 summary/abstract。当前项目中有用："
            "当全文抓取未请求、失败或抽取为空时，ArxivPaperSearchTool 会使用该字段作为 fallback content；"
            "如果全文抓取成功，则该字段仍会保留在 metadata 的 `paper_summary` 中。"
        ),
    )
    published_at: datetime | None = Field(
        default=None,
        description=(
            "可选字段。论文原始发布时间。当前项目中有用：tool 会写入 `SourceReference.published_at`，"
            "并以 ISO 字符串放入 normalized item metadata；如果 provider 未提供则为空。它不是系统检索时间。"
        ),
    )
    updated_at: datetime | None = Field(
        default=None,
        description=(
            "可选字段。provider 返回的论文最后更新时间。当前项目中有用：ArxivPaperSearchTool 会以 ISO 字符串写入 "
            "normalized item metadata，用于 freshness/provenance 判断；当前不会直接写入 SourceReference.published_at。"
        ),
    )
    arxiv_id: str = Field(
        min_length=1,
        description=(
            "必填字段。论文的 canonical arXiv ID，不能为空字符串。当前项目中有用："
            "ArxivPaperSearchTool 会优先用它构造 `SourceReference.source_id`，并设置 `source_id_type='arxiv_id'`；"
            "content fetch request 也会用它解析 PDF URL。"
        ),
    )
    primary_category: str | None = Field(
        default=None,
        description=(
            "可选字段。论文的 primary arXiv category。当前项目中有用：tool 会把它写入 `SourceReference.metadata` "
            "和 normalized item metadata，帮助后续筛选或解释论文领域；若 provider 未返回则为空。"
        ),
    )
    categories: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。论文关联的所有 arXiv category。当前项目中有用："
            "tool 会把它写入 `SourceReference.metadata` 和 normalized item metadata，用于 provenance、过滤或调试。"
        ),
    )
    url: str | None = Field(
        default=None,
        description=(
            "可选字段。论文 abstract/detail 页面 URL。当前项目中有用：ArxivPaperSearchTool 会把它写入 "
            "`SourceReference.source_url` 和 metadata 的 `paper_url`；它通常是可展示 citation 链接，不一定是 PDF URL。"
        ),
    )
    pdf_url: str | None = Field(
        default=None,
        description=(
            "可选字段。provider 返回的 PDF 下载 URL。当前项目中有用：ArxivPaperSearchTool 会把它传给 "
            "`PaperContentFetchRequest.pdf_url`，并写入 `SourceReference.metadata['pdf_url']` 和 normalized item metadata。"
            "如果为空但有 arXiv ID，content fetch adapter 仍可尝试由 arXiv ID 解析 PDF URL。"
        ),
    )
    doi_url: str | None = Field(
        default=None,
        description=(
            "可选字段。论文关联的 DOI URL。当前项目中有用：tool 会写入 `SourceReference.metadata['doi_url']` "
            "和 normalized item metadata；当前不会把它作为 `SourceReference.source_url` 的主 URL，因为 arXiv abstract URL "
            "更适合作为当前 paper_search provenance 的 canonical 展示入口。"
        ),
    )
    source: str = Field(
        default="arxiv",
        description=(
            "可选字段，默认 `arxiv`。paper search provider 名称。当前项目中有用："
            "ArxivPaperSearchTool 会把它写入 `SourceReference.metadata['source']` 和 normalized item metadata 的 "
            "`paper_source_name`。它表示检索 provider，不是论文 publisher，也不应写入 `SourceReference.publisher`。"
        ),
    )
