"""paper_content_fetch adapter 的标准化输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaperContentFetchRequest(BaseModel):
    """paper content fetch adapter 的 typed paper ID 输入。

    当前项目中该模型由 `ArxivPaperSearchTool` 为选中的 paper search 候选构造，并传给
    `PaperContentFetchClientProtocol.fetch_content(...)`。它通过 `paper_id + paper_id_type`
    定位要下载/解析的论文全文来源，不表达 retrieval family、tool selection 或 evidence processing 语义。
    当前唯一实现是 `ArxivPaperContentFetchClient`，因此当前只接受 `paper_id_type='arxiv_id'`。
    """

    paper_id: str = Field(
        min_length=1,
        description=(
            "必填字段。待抓取论文在 `paper_id_type` 命名空间内的稳定 ID 值，不能为空字符串。"
            "当前项目中有用：ArxivPaperSearchTool 会传入 `PaperSearchResult.paper_id`，当前通常是 arXiv ID，"
            "例如 `2501.12345v2`；ArxivPaperContentFetchClient 会用该值构造 arXiv PDF URL。"
        ),
    )
    paper_id_type: str = Field(
        min_length=1,
        description=(
            "必填字段。`paper_id` 的 ID 类型或命名空间，不能为空字符串。当前项目中有用："
            "ArxivPaperSearchTool 会传入 `PaperSearchResult.paper_id_type`；当前 ArxivPaperContentFetchClient "
            "只接受 `arxiv_id`，其它值会被拒绝。"
        ),
    )
