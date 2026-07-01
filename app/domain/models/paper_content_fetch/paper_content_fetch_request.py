"""paper_content_fetch adapter 的标准化输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaperContentFetchRequest(BaseModel):
    """paper content fetch adapter 的 provider-neutral 输入。

    当前项目中该模型由 `ArxivPaperSearchTool` 为选中的 paper search 候选构造，并传给
    `PaperContentFetchClientProtocol.fetch_content(...)`。它只负责定位要下载/解析的论文全文来源，
    不表达 retrieval family、tool selection 或 evidence processing 语义。
    """

    arxiv_id: str | None = Field(
        default=None,
        description=(
            "可选字段。arXiv 论文 ID，例如 `2501.12345` 或 `2501.12345v2`。当前项目中有用："
            "ArxivPaperSearchTool 会在 `PaperSearchResult.paper_id_type == 'arxiv_id'` 时从 `paper_id` 派生并填充它；"
            "arXiv content fetch adapter 可用它解析出 PDF URL。"
            "当调用方直接提供 `pdf_url` 时，该字段可以为空。"
        ),
    )
    pdf_url: str | None = Field(
        default=None,
        description=(
            "可选字段。可直接下载的论文 PDF URL。当前项目中有用：ArxivPaperSearchTool 会从 `PaperSearchResult.pdf_url` "
            "透传它；content fetch adapter 会优先或辅助使用该 URL 下载 PDF 并抽取文本。若只有 `arxiv_id` 而没有 URL，也可以为空。"
        ),
    )
    paper_id: str | None = Field(
        default=None,
        description=(
            "可选字段。调用方提供的稳定 paper 标识。当前项目中有用：ArxivPaperSearchTool 会传入 `PaperSearchResult.paper_id`，"
            "用于把 fetch result 与原始 search result 对齐，也会进入后续 normalized item metadata。该字段不是 provider URL，"
            "也不一定等同于 arXiv ID。"
        ),
    )
