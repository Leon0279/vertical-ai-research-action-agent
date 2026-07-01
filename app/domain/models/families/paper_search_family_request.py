"""paper_search family service 的标准化输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaperSearchFamilyRequest(BaseModel):
    """`PaperSearchFamilyService.run(...)` 的 family 层标准化输入。

    这个模型由 Tool Execution Layer 根据已生成的 `selected_family='paper_search'`
    和 retrieval query 映射而来，不是 arXiv tool 的原始请求，也不是 paper_search adapter
    的 provider 请求。它负责把 paper_search family 需要的 query、数量限制和可选 tool hint
    传给 family service；family service 再选择具体 tool，目前是 `arxiv_paper_search_v1`。
    """

    query_text: str = Field(
        min_length=1,
        description=(
            "必填字段。paper_search family 本次要执行的论文检索 query，不能为空字符串。"
            "当前项目中有用：ToolExecutionLayerService 会把 RetrievalQueryGenerationService 生成的 "
            "`generated_query` 映射到这里；PaperSearchFamilyService 会规范化空白后传给 "
            "`ArxivPaperSearchToolRequest.query_text`。该字段只表达 retrieval query，不包含 selected_tool，"
            "也不包含最终 evidence synthesis 语义。"
        ),
    )
    max_search_results: int = Field(
        default=5,
        ge=1,
        description=(
            "可选字段，默认 5，必须大于等于 1。paper_search family 允许底层 paper tool 最多保留多少条论文搜索候选。"
            "当前项目中有用：ToolExecutionLayerService 可从上游 request 约束映射该值；PaperSearchFamilyService 会透传给 "
            "`ArxivPaperSearchToolRequest.max_search_results`；ArxivPaperSearchTool 再用它设置 `PaperSearchQuery.limit`，"
            "并限制最终 normalized_items 的候选范围。它控制 metadata search 候选数量，不等同于全文抓取数量。"
        ),
    )
    max_content_fetches: int = Field(
        default=3,
        ge=0,
        description=(
            "可选字段，默认 3，必须大于等于 0。paper_search family 允许底层 paper tool 对多少条候选论文执行全文抓取。"
            "当前项目中有用：PaperSearchFamilyService 会透传给 `ArxivPaperSearchToolRequest.max_content_fetches`；"
            "ArxivPaperSearchTool 会从 paper search candidates 中选择最多该数量且 `paper_id_type='arxiv_id'` 的候选，"
            "调用 ArxivPaperContentFetchClient 抽取 PDF 文本。值为 0 时不会抓取全文，tool 会使用论文摘要作为候选材料内容。"
        ),
    )
    preferred_tool: str | None = Field(
        default=None,
        description=(
            "可选字段。上游传入的 family 内 preferred tool id。当前项目中有用：ToolExecutionLayerService 会把 "
            "Research Executor-owned `preferred_tool` 原样传到这里；PaperSearchFamilyService 只用它在当前 family 的 tool registry "
            "中匹配具体 tool，不会自行合成、覆盖或从上一次 selected_tool 反推该值。当前合法值通常是 "
            "`arxiv_paper_search_v1`；为空时 family 使用默认 tool。若传入不可用 tool，family 会返回 failed result。"
        ),
    )
