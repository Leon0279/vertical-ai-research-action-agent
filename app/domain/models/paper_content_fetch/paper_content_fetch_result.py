"""paper_content_fetch adapter 的标准化输出模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PaperContentExtractionStatus = Literal[
    "succeeded",
    "empty_text",
    "download_failed",
    "extraction_failed",
]


class PaperContentFetchResult(BaseModel):
    """paper content fetch adapter 返回的标准化全文抓取结果。

    当前项目中该模型由 arXiv paper content fetch adapter 返回给 `ArxivPaperSearchTool`。tool 会根据
    `extraction_status` 决定是否使用 `extracted_text` 替代 paper summary，并把抓取状态写入
    `NormalizedRetrievalItem.metadata`、`RetrievalExecutionSummary.metrics` 和 `RetrievalTrace.observability`。
    """

    paper_id: str = Field(
        min_length=1,
        description=(
            "必填字段。被抓取论文的稳定标识，不能为空字符串。当前项目中有用："
            "content fetch adapter 会优先沿用 `PaperContentFetchRequest.paper_id`，若缺失则可由 arXiv ID 或 PDF URL 派生；"
            "ArxivPaperSearchTool 用它帮助关联 fetch result 和原始 paper search 候选。"
        ),
    )
    arxiv_id: str | None = Field(
        default=None,
        description=(
            "可选字段。论文的 arXiv ID。当前项目中有用：当 request 或解析过程知道 arXiv ID 时填充，"
            "用于 provenance、metadata 和调试；如果 content fetch 是通过非 arXiv PDF URL 发起，则可以为空。"
        ),
    )
    source_url: str = Field(
        min_length=1,
        description=(
            "必填字段。实际用于下载和解析的 PDF URL，不能为空字符串。当前项目中有用："
            "ArxivPaperSearchTool 会把它作为 content fetch provenance 写入 normalized item metadata；"
            "该字段表示全文抓取来源，不一定等同于 paper abstract URL。"
        ),
    )
    extracted_text: str | None = Field(
        default=None,
        description=(
            "可选字段。PDF 解析得到的正文文本。当前项目中有用：当 `extraction_status='succeeded'` 且该字段非空时，"
            "ArxivPaperSearchTool 会用它作为 `NormalizedRetrievalItem.content`，并把 `content_type` 设为 `document_chunk`；"
            "当抽取为空或失败时，该字段通常为空，tool 会回退使用 paper summary。"
        ),
    )
    extraction_status: PaperContentExtractionStatus = Field(
        description=(
            "必填字段。PDF 下载与文本抽取的状态。当前项目中有用：`succeeded` 表示成功抽取文本；"
            "`empty_text` 表示下载/解析流程完成但没有得到可用正文；`download_failed` 表示 PDF 下载失败；"
            "`extraction_failed` 表示下载后文本抽取失败。ArxivPaperSearchTool 会基于该字段统计 fetch_success/empty/failed，"
            "并决定是否 partial_success。"
        ),
    )
    error_info: str | None = Field(
        default=None,
        description=(
            "可选字段。adapter 层的简短失败或降级原因。当前项目中有用：当 `extraction_status` 不是 `succeeded` "
            "或抽取质量降级时填充，例如下载失败原因、解析异常摘要、空文本说明。成功路径通常为空。"
            "该字段不应存放完整 traceback 或大型 raw response。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。paper content fetch 的 provider-specific 轻量 metadata。当前项目中有用："
            "arXiv content fetch adapter 当前可能放入 `download_url`（最终下载 URL）、`content_type`（HTTP content type）、"
            "`content_length` 或 `download_bytes`（下载大小）、`extractor`（文本抽取方式）、`page_count`（如果 provider/解析器可得）、"
            "`raw_status_code` 或其它诊断信息。ArxivPaperSearchTool 会把该 dict merge 到 normalized item metadata 中。"
            "稳定主字段应优先提升为正式字段，不应长期只塞在 metadata。"
        ),
    )
    source: str = Field(
        default="arxiv",
        description=(
            "可选字段，默认 `arxiv`。content fetch 来源/provider 名称。当前项目中有用："
            "ArxivPaperSearchTool 会把它写入 normalized item metadata 的 `content_fetch_source`，用于区分正文来自哪个抓取实现；"
            "它不是论文 publisher，也不是 SourceReference.source_type。"
        ),
    )
