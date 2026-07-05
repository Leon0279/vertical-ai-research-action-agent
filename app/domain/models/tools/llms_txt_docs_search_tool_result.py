"""llms_txt_docs_search tool 的运行时输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import AcquisitionStatus
from app.domain.models.retrieval import (
    NormalizedRetrievalItem,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)


class LlmsTxtDocsSearchToolResult(BaseModel):
    """docs_search tool 的标准化执行结果。

    当前项目中该模型会被 DocsSearchFamilyService 包装成 family result，
    再继续进入 ToolExecutionLayerService、RequestCompletionEvaluationService、
    EvidenceProcessingService 和未来新版 Research Executor 链路。它只描述 tool
    执行结果，不表示最终答案，也不负责 evidence synthesis。
    """

    normalized_items: list[NormalizedRetrievalItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。docs search tool 归一化后的候选材料主数据。当前项目中该字段有用："
            "DocsSearchFamilyService 会原样带入 family result，ToolExecutionLayerService 会将最终 "
            "normalized_items 暴露给 EvidenceProcessingService；EvidenceProcessingService 会读取每个 "
            "NormalizedRetrievalItem 的 content、source_family、source_references 和 metadata。"
            "当 acquisition_status 为 no_result 或 failed 时通常为空。"
        ),
    )
    acquisition_status: AcquisitionStatus = Field(
        description=(
            "必填字段。tool 本次获取信息的整体状态。当前项目中该字段有用：family service、"
            "ToolExecutionLayerService 和 RequestCompletionEvaluationService 都依赖它判断当前 retrieval "
            "是否成功、是否部分成功、是否无结果或失败。取值含义：success 表示成功获得可用材料；"
            "partial_success 表示获得了部分材料但存在丢弃或降级；no_result 表示没有可用材料；"
            "failed 表示 adapter 调用或 tool 执行失败。"
        ),
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。adapter 或 tool 归一化过程中丢弃的 item 数量。"
            "当前项目中该字段有用：family / TEL 会保留该统计，EvidenceProcessingService 的 summary "
            "会记录 upstream_dropped_item_count；它也用于解释 partial_success 的降级来源。"
        ),
    )
    source_summary: RetrievalSourceSummary = Field(
        default_factory=RetrievalSourceSummary,
        description=(
            "可选字段，默认空 RetrievalSourceSummary。来源与 provenance 的摘要。当前项目中该字段有用："
            "docs tool 会设置 selected_family=docs_search、selected_tool=llms_txt_docs_search_v1、"
            "normalized_count；adapter 返回的 source_summary.metadata 中当前可包含 searched_sub_source_types，"
            "表示实际搜索过的 docs 子来源类型。family / TEL / EvidenceProcessing 可读取其中的 selected_tool "
            "和 selected_family 作为 provenance。"
        ),
    )
    execution_summary: RetrievalExecutionSummary = Field(
        default_factory=RetrievalExecutionSummary,
        description=(
            "可选字段，默认空 RetrievalExecutionSummary。执行统计和恢复相关可观测信息。当前项目中该字段有用："
            "docs tool 会设置 normalized_count、dropped_item_count，并在 metrics 中写入 search_result_count；"
            "family 和 TEL 会在此基础上补充 candidate_tool_count、retry_count、fallback_applied、"
            "recovery_attempt_count 等信息。该字段用于调试、评估 request completion 和解释降级，不承载原始 provider payload。"
        ),
    )
    retrieval_trace: RetrievalTrace = Field(
        default_factory=RetrievalTrace,
        description=(
            "可选字段，默认空 RetrievalTrace。轻量 retrieval 轨迹。当前项目中该字段有用：docs tool 会写入 "
            "target_problem、returned_refs，并在 context 中写入 query_text 和 selected_sub_source_types；"
            "失败路径会在 errors 中写入 search_error。family / TEL 可能继续补充 selected_family、selected_tool、"
            "generated_query、query_focus、attempts 等字段。该字段用于后续 EvidenceProcessing 的语境读取和运行时诊断。"
        ),
    )
    error_info: str | None = Field(
        default=None,
        description=(
            "可选字段。tool 顶层失败摘要。当前项目中该字段有用：当 acquisition_status=failed 时，"
            "LlmsTxtDocsSearchTool 会把 adapter 调用异常转成简短字符串放在这里；family / TEL 会保留该错误，"
            "用于失败结果和 recovery evaluation。该字段不应放 provider 原始响应、HTML、完整 stack trace 或大型 debug payload。"
        ),
    )
