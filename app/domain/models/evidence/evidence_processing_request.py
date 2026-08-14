"""Evidence Processing Service 的输入模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.domain.enums import AcquisitionStatus
from app.domain.models.retrieval import (
    NormalizedRetrievalItem,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)

if TYPE_CHECKING:
    from app.domain.models.tool_execution_layer.tool_execution_layer_result import (
        ToolExecutionLayerResult,
    )


class EvidenceProcessingRequest(BaseModel):
    """把 Tool Execution Layer 最终输出转换为 evidence units 的标准化输入。

    该模型是新版 EvidenceProcessingService 的公开输入边界，通常由
    `EvidenceProcessingRequest.from_tool_execution_result(...)` 从 ToolExecutionLayerResult 构造。
    它只消费 TEL 最终稳定输出，不读取 TEL 内部的 FamilySelectionResult、RetrievalQueryGenerationResult、
    BaseFamilyExecutionResult 或 RequestCompletionEvaluationResult。

    当前项目中该模型有用：未来新版 Research Executor 会把 ToolExecutionLayerService 返回的 candidate materials
    交给 EvidenceProcessingService 做 material-level dedup、质量过滤、evidence structuring 和本轮 evidence consolidation。
    它不负责重新执行 retrieval、不生成 final answer、不做 memory write-back。
    """

    normalized_items: list[NormalizedRetrievalItem] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。Tool Execution Layer 最终返回的标准化候选材料列表。当前项目中有用："
            "EvidenceProcessingService 会把它作为主输入，先按 item_id、primary source ref + normalized content、"
            "same-source containment 做 deterministic dedup，再做质量过滤、LLM structuring 或 deterministic fallback。"
            "每个元素是 NormalizedRetrievalItem，包含 item_id、source_family、source_references、content、content_type、metadata。"
            "source_references 是正式 provenance 列表；metadata 中保留 tool/provider-specific 附加信息。为空时会短路返回 processing_status='no_result'。"
        ),
    )
    acquisition_status: AcquisitionStatus = Field(
        description=(
            "必填字段。上游 Tool Execution Layer 的最终 acquisition status。当前项目中有用：EvidenceProcessingService 会在进入 material processing "
            "前检查该字段；当值为 AcquisitionStatus.NO_RESULT 或 AcquisitionStatus.FAILED 时，会短路返回空 evidence result，"
            "processing_status='no_result'，并在 evidence_processing_summary.short_circuit_reason 中记录原因。"
            "success / partial_success 才会继续处理 normalized_items。该字段表示 retrieval 获取结果状态，不等同于 EvidenceProcessingResult.processing_status。"
        ),
    )
    dropped_item_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。上游 TEL / family / tool 在进入 Evidence Processing 前已经丢弃的 item 数量。"
            "当前项目中有用：EvidenceProcessingService 会把它写入 EvidenceProcessingSummary.upstream_dropped_item_count，"
            "用于区分“retrieval 阶段丢弃的候选材料”和“evidence processing 阶段丢弃的材料”。"
        ),
    )
    source_summary: RetrievalSourceSummary = Field(
        default_factory=RetrievalSourceSummary,
        description=(
            "可选字段，默认空 RetrievalSourceSummary。来自 ToolExecutionLayerResult.source_summary 的来源摘要。当前项目中有用："
            "EvidenceProcessingService 会在 normalized item 缺少 source_family 或 evidence unit metadata 需要 provenance 时读取它。"
            "该对象正式字段包括 selected_family、selected_tool、normalized_count、metadata；metadata 可包含 tool/adapter-specific 来源摘要，"
            "例如 docs 的 searched_sub_source_types、web/paper provider 信息、memory recall scope 摘要等。"
            "selected_tool 不在 TEL 顶层暴露，但可通过该字段作为 evidence unit metadata 的 provenance。"
        ),
    )
    execution_summary: RetrievalExecutionSummary = Field(
        default_factory=RetrievalExecutionSummary,
        description=(
            "可选字段，默认空 RetrievalExecutionSummary。来自 ToolExecutionLayerResult.execution_summary 的执行摘要。当前项目中有用："
            "EvidenceProcessingRequest 会保留它作为上游执行上下文，当前 EvidenceProcessingService 主要把上游 acquisition_status 和 dropped_item_count "
            "写入自己的 processing summary；该字段本身可供未来 Research Executor 或诊断流程查看 TEL 的 retry_count、fallback_applied、"
            "recovery_attempt_count、recovery_exhausted_reason、metrics、observability 等信息。"
            "它不驱动 evidence structuring 的核心分支，不应在这里塞入 evidence-level 输出。"
        ),
    )
    retrieval_trace: RetrievalTrace = Field(
        default_factory=RetrievalTrace,
        description=(
            "可选字段，默认空 RetrievalTrace。来自 ToolExecutionLayerResult.retrieval_trace 的轻量检索轨迹。当前项目中有用："
            "EvidenceProcessingService 会读取其中的 target_problem、target_scope、evidence_goal、sub_question、comparison_candidate、gap "
            "并写入 ProcessedEvidenceUnit 对应字段；还会读取 selected_tool、generated_query 写入 evidence unit metadata；"
            "当 material.source_family 为空时，也会从 retrieval_trace.selected_family 作为 fallback provenance。"
            "该对象还可能包含 attempts、returned_refs、errors、context、observability，用于保留 TEL/family/tool 的检索上下文和诊断信息。"
        ),
    )

    @classmethod
    def from_tool_execution_result(
        cls,
        result: ToolExecutionLayerResult,
    ) -> "EvidenceProcessingRequest":
        """从 Tool Execution Layer 最终结果构造证据处理请求。

        Args:
            result (ToolExecutionLayerResult): TEL 输出的归一化候选材料、获取状态、执行摘要和检索追踪信息。

        Returns:
            EvidenceProcessingRequest: 可直接传入 EvidenceProcessingService 的请求，保留 TEL 输出中的处理所需字段。
        """

        return cls(
            normalized_items=result.normalized_items,
            acquisition_status=result.acquisition_status,
            dropped_item_count=result.dropped_item_count,
            source_summary=result.source_summary,
            execution_summary=result.execution_summary,
            retrieval_trace=result.retrieval_trace,
        )
