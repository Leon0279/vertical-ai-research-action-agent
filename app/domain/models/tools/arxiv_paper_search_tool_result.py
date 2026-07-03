"""arxiv_paper_search tool 的标准化输出模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models.retrieval import (
    NormalizedRetrievalItem,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)

AcquisitionStatus = Literal["success", "partial_success", "no_result", "failed"]


class ArxivPaperSearchToolResult(BaseModel):
    """`ArxivPaperSearchTool.run(...)` 返回的标准化运行时输出。

    这个模型是 paper_search tool 层的结果，会被 `PaperSearchFamilyService` 包装为
    family-level result，再继续传给 Tool Execution Layer、RequestCompletionEvaluationService
    和后续 EvidenceProcessingService。它承载的是 retrieval candidate materials 和执行摘要，
    不负责最终 evidence synthesis，也不生成最终答案。
    """

    normalized_items: list[NormalizedRetrievalItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。paper tool 输出的标准化候选材料主数据。当前项目中有用："
            "每个 item 通常对应一篇 paper 的摘要或抓取后的全文片段，`source_references` 会指向 paper 原始来源，"
            "`metadata` 会保留 paper_id、paper_id_type、arxiv_id（当 paper_id_type 为 arxiv_id 时）、category、PDF URL、"
            "fetch 状态等 paper-specific 信息。"
            "下游 family/TEL/EvidenceProcessing 会继续消费这个字段。"
        ),
    )
    acquisition_status: AcquisitionStatus = Field(
        description=(
            "必填字段。paper tool 本次获取材料的总体状态。当前项目中有用：`success` 表示 search 和必要 fetch "
            "整体可用；`partial_success` 表示有候选但全文抓取部分失败、为空或未请求；`no_result` 表示没有 paper search "
            "候选；`failed` 表示 search adapter 调用等关键步骤失败。family/TEL/evaluator 会依赖该字段判断是否需要 recovery。"
        ),
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。tool-level normalization 阶段丢弃的候选数量。"
            "当前项目中有用：用于解释 partial_success 或数据质量下降。当前 ArxivPaperSearchTool 通常不主动丢弃 "
            "paper search results，因此多为 0；但该字段仍作为跨 tool 统一输出结构保留。"
        ),
    )
    source_summary: RetrievalSourceSummary = Field(
        default_factory=RetrievalSourceSummary,
        description=(
            "可选字段，默认空 `RetrievalSourceSummary` 对象。来源/provenance 摘要。当前项目中有用："
            "ArxivPaperSearchTool 会写入 `selected_family='paper_search'`、`selected_tool='arxiv_paper_search_v1'` "
            "和 `normalized_count`；provider-specific 来源覆盖信息如果未来出现，应放入 `source_summary.metadata`，"
            "不要再平铺成裸 dict 主字段。"
        ),
    )
    execution_summary: RetrievalExecutionSummary = Field(
        default_factory=RetrievalExecutionSummary,
        description=(
            "可选字段，默认空 `RetrievalExecutionSummary` 对象。执行统计和降级信号。当前项目中有用："
            "ArxivPaperSearchTool 当前会在正式字段写入 `normalized_count`、`dropped_item_count`，并在 `metrics` 中写入 "
            "`search_result_count`、`selected_for_fetch_count`、`fetch_success_count`、`fetch_empty_count`、"
            "`fetch_failed_count`。这些计数会帮助 family/TEL/evaluator 判断本次 retrieval 的质量与是否 partial_success。"
        ),
    )
    retrieval_trace: RetrievalTrace = Field(
        default_factory=RetrievalTrace,
        description=(
            "可选字段，默认空 `RetrievalTrace` 对象。轻量检索轨迹。当前项目中有用："
            "ArxivPaperSearchTool 当前会把 paper-specific 过程信息放入 `observability`，包括 `attempted_papers`、"
            "`selected_for_fetch`、`fetched_papers`、`failed_fetches`；失败路径会在 `errors['search_error']` 中记录简短错误。"
            "该字段用于调试和 provenance，不替代 `normalized_items[*].source_references`。"
        ),
    )
    error_info: str | None = Field(
        default=None,
        description=(
            "可选字段。tool 级失败摘要。当前项目中有用：当 `acquisition_status='failed'` 时写入简短错误信息，"
            "例如 paper_search adapter 调用异常；成功、部分成功或 no_result 场景通常为空。该字段不应承载大型 provider raw payload "
            "或完整 traceback，详细调试信息应放入 trace/observability。"
        ),
    )
