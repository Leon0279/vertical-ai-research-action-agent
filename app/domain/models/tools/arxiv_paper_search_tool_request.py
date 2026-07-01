"""arxiv_paper_search tool 的运行时输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ArxivPaperSearchToolRequest(BaseModel):
    """`ArxivPaperSearchTool.run(...)` 的标准化运行时输入。

    这个模型位于 tool 层，不是 paper_search adapter 的原始请求，也不是 family/TEL 的顶层
    request。当前项目中它通常由 `PaperSearchFamilyService` 根据 `PaperSearchFamilyRequest`
    映射生成，用来驱动 arXiv paper metadata search 和后续 paper content fetch。
    """

    query_text: str = Field(
        min_length=1,
        description=(
            "必填字段。paper tool 实际执行的检索 query，不能为空字符串。当前项目中有用："
            "由 Tool Execution Layer 的 query generation 产出，再经 paper_search family 透传到这里；"
            "ArxivPaperSearchTool 会用它构造 `PaperSearchQuery.query_text`，发送给 paper_search adapter。"
        ),
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description=(
            "可选字段，默认 5，必须大于等于 1。表示 paper_search adapter 最多返回并保留多少条论文候选。"
            "当前项目中有用：ArxivPaperSearchTool 会把它传给 `PaperSearchQuery.limit`，并用它限制后续 "
            "normalized_items 的候选范围；它控制的是 metadata search 的候选数量，不等同于全文抓取数量。"
        ),
    )
    max_content_fetches: int = Field(
        default=3,
        ge=0,
        description=(
            "可选字段，默认 3，必须大于等于 0。表示最多对多少条 paper search 候选执行全文抓取。"
            "当前项目中有用：ArxivPaperSearchTool 会从 search results 中选择最多该数量的候选，调用 "
            "paper_content_fetch adapter；值为 0 时表示只使用论文摘要/metadata，不请求 PDF/full text。"
        ),
    )
