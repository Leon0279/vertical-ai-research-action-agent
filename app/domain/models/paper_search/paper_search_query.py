"""paper_search adapter 的标准化查询输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaperSearchQuery(BaseModel):
    """paper search adapter 的 provider-neutral 输入。

    当前项目中该模型由 `ArxivPaperSearchTool` 构造，并传给 `PaperSearchClientProtocol.search_papers(...)`。
    它只描述 paper metadata search 的查询与分页，不负责全文抓取，也不表达 family/tool selection。
    """

    query_text: str = Field(
        min_length=1,
        description=(
            "必填字段。用于检索论文 metadata 的自由文本 query，不能为空字符串。当前项目中有用："
            "由 ArxivPaperSearchTool 从 `ArxivPaperSearchToolRequest.query_text` 映射而来，arXiv paper_search adapter "
            "会将它转换成 provider 查询参数。该字段只用于论文搜索，不用于 PDF/full text 抓取。"
        ),
    )
    limit: int = Field(
        default=5,
        description=(
            "可选字段，默认 5。当前页最多返回多少条 paper search result。当前项目中有用："
            "ArxivPaperSearchTool 会用 `max_search_results` 设置它；paper_search adapter 会据此限制 provider 返回数量。"
            "它控制的是 search metadata 结果数量，不控制 content fetch 数量。"
        ),
    )
    start: int = Field(
        default=0,
        description=(
            "可选字段，默认 0。分页检索的 0-based 起始 offset。当前项目中有用但使用较轻："
            "当前 ArxivPaperSearchTool 第一版通常只请求第一页，因此传入 0；paper_search adapter 仍保留该字段，以支持 provider "
            "分页能力和未来多页检索。"
        ),
    )
