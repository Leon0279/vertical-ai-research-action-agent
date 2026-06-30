"""family execution result 的共享基类模型。"""

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


class BaseFamilyExecutionResult(BaseModel):
    """四个 retrieval family result 共用的稳定输出骨架。

    该模型承载 family service 完成一次 tool execution 后的统一 outcome。
    它不是具体 tool result，不是 ToolExecutionLayerResult，也不是 EvidenceProcessingResult；
    它位于 family service 与 ToolExecutionLayerService / RequestCompletionEvaluationService 之间。
    当前 docs_search、paper_search、web_search、research_knowledge_recall 的 family result 都继承该基类。
    """

    normalized_items: list[NormalizedRetrievalItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。family 本次执行产出的标准化候选材料。当前项目中该字段有用："
            "family service 通常从底层 tool result 原样透传 normalized_items；ToolExecutionLayerService 会把最终 family result "
            "中的 normalized_items 暴露给 ToolExecutionLayerResult；EvidenceProcessingService 会消费这些 item 进行 dedup、"
            "structuring 和 evidence unit 生成。no_result 或 failed 时通常为空。"
        ),
    )
    acquisition_status: AcquisitionStatus = Field(
        description=(
            "必填字段。family 本次执行的信息获取状态。当前项目中该字段有用：ToolExecutionLayerService 会把它传给 "
            "RequestCompletionEvaluationService；evaluator 依赖 success、partial_success、no_result、failed 判断当前 request "
            "是否完成、是否需要 retry/fallback/stop。该字段通常来自底层 tool result，但 family 失败路径也会直接设置 failed。"
        ),
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。tool 或 family 层归一化过程中丢弃的 item 数量。当前项目中该字段有用："
            "family 通常从 tool result 透传；ToolExecutionLayerService 和 EvidenceProcessingService 会保留它用于统计、"
            "解释 partial_success 和观察上游 acquisition 降级。"
        ),
    )
    source_summary: RetrievalSourceSummary = Field(
        default_factory=RetrievalSourceSummary,
        description=(
            "可选字段，默认空 RetrievalSourceSummary。family 级来源/provenance 摘要。当前项目中该字段有用："
            "family service 会确保 selected_family 和 selected_tool 反映 family 内部选择结果，并保留 normalized_count。"
            "docs_search family 当前还会保留 tool/adapter 带来的 metadata，例如 searched_sub_source_types；其它 family 可保留 "
            "source coverage 或 provider-specific 摘要。ToolExecutionLayerService、EvidenceProcessingService 会读取其中的 "
            "selected_family / selected_tool 作为 provenance。"
        ),
    )
    execution_summary: RetrievalExecutionSummary = Field(
        default_factory=RetrievalExecutionSummary,
        description=(
            "可选字段，默认空 RetrievalExecutionSummary。family 执行统计和 family-level selection 信号。当前项目中该字段有用："
            "family 会在底层 tool execution_summary 基础上补充 metrics['candidate_tool_count']，表示本次 family registry 中可选 tool 数量；"
            "docs_search family 还会在 observability['preferred_tool_requested'] 中记录上游请求的 preferred_tool。"
            "ToolExecutionLayerService 之后可能继续补 retry_count、fallback_applied、recovery_attempt_count、recovery_exhausted_reason 等 TEL 统计。"
        ),
    )
    retrieval_trace: RetrievalTrace = Field(
        default_factory=RetrievalTrace,
        description=(
            "可选字段，默认空 RetrievalTrace。family selection 与底层 tool execution 的轻量轨迹。当前项目中该字段有用："
            "family 会在 tool trace 基础上补 selected_family、selected_tool，并在 context 中保留 candidate_tools、preferred_tool。"
            "docs_search family failed 路径还会把 query_text、target_problem、freshness_requirement、sub_source_types 写入 context，"
            "并将 family_error 归入 errors。ToolExecutionLayerService 会继续补 generated_query、query_focus、attempts 等信息。"
        ),
    )
    error_info: str | None = Field(
        default=None,
        description=(
            "可选字段。family 顶层错误摘要。当前项目中该字段有用：当 family 内没有可用 tool、preferred_tool 不存在、"
            "底层 tool failed 或 family execution 出错时，family/TEL 会保留该简短错误。该字段不应承载 provider raw payload、"
            "大型调试对象或完整 stack trace；详细诊断应放 retrieval_trace.errors 或 observability。"
        ),
    )
    selected_family: str = Field(
        description=(
            "必填字段。当前 family result 对应的 retrieval family。当前项目中该字段有用：ToolExecutionLayerService 和 "
            "RequestCompletionEvaluationService 会要求 request.selected_family 与 execution_outcome.selected_family 一致，"
            "以避免把某个 family 的结果误当成另一个 family 的 outcome。具体子类会设置默认值，例如 DocsSearchFamilyResult 默认为 docs_search。"
        ),
    )
    candidate_tools: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。family 内本次可供选择的 tool id 列表。当前项目中该字段有用："
            "DocsSearchFamilyService 会从 tool registry 生成该列表，当前通常包含 llms_txt_docs_search_v1；"
            "RequestCompletionEvaluationService 会使用 candidate_tools 与 selected_tool 判断 same-family fallback 是否理论可用。"
            "如果 family 没有注册任何 tool，该字段为空且结果通常为 failed。"
        ),
    )
    selected_tool: str | None = Field(
        default=None,
        description=(
            "可选字段。family 内部实际选择并执行的 tool id。当前项目中该字段有用：ToolExecutionLayerService 自身不负责选择 concrete tool，"
            "也不在顶层 result 暴露 selected_tool；但 family result 需要保留它作为 provenance，并供 RequestCompletionEvaluationService "
            "判断 same-family fallback 是否可能。docs_search family 当前通常为 llms_txt_docs_search_v1；当没有可用 tool 或 preferred_tool "
            "非法时可为空。"
        ),
    )
