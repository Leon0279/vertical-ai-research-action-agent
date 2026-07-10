"""Evidence Processing Service 的输出模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models.evidence.evidence_processing_summary import EvidenceProcessingSummary
from app.domain.models.evidence.processed_evidence_summary import ProcessedEvidenceSummary
from app.domain.models.evidence.processed_evidence_unit import ProcessedEvidenceUnit

EvidenceProcessingStatus = Literal["success", "partial_success", "no_result", "failed"]


class EvidenceProcessingResult(BaseModel):
    """把当前轮 candidate materials 转换为 processed evidence units 后的结果。

    该模型是新版 EvidenceProcessingService 的公开输出边界，面向未来新版 Research Executor
    以及后续 finding / synthesis / conclusion 阶段。它表达的是“当前轮材料被处理成了哪些结构化 evidence”，
    不表示最终结论，也不执行 memory write-back。
    """

    processed_evidence_units: list[ProcessedEvidenceUnit] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。当前轮 evidence processing 产出的结构化 evidence units。当前项目中有用："
            "这是 EvidenceProcessingResult 的主数据，后续 Research Executor / synthesis 阶段会消费它们。"
            "每个元素是 ProcessedEvidenceUnit，包含 evidence_unit_id、source_ref、source_family、source_type、content、evidence_type、"
            "support_refs、target_problem、target_scope、evidence_goal、sub_question、comparison_candidate、gap、metadata。"
            "当上游 no_result/failed、输入为空、全部材料质量不足或处理失败时，该列表为空。"
        ),
    )
    evidence_summary: ProcessedEvidenceSummary = Field(
        default_factory=ProcessedEvidenceSummary,
        description=(
            "可选字段，默认空 ProcessedEvidenceSummary。当前轮 evidence 输出的轻量结果摘要。当前项目中有用："
            "用于快速了解产出了多少 evidence、各 evidence_type 分布，以及覆盖了哪些 source families / source types。"
            "该对象正式字段包括 new_evidence_count、evidence_type_breakdown、source_coverage_summary、metadata；"
            "source_coverage_summary 当前包含 source_families 和 source_types 两个 key。该字段是结果摘要，不替代 processed_evidence_units。"
        ),
    )
    evidence_processing_summary: EvidenceProcessingSummary = Field(
        default_factory=EvidenceProcessingSummary,
        description=(
            "可选字段，默认空 EvidenceProcessingSummary。EvidenceProcessingService 本轮处理过程的计数和可观测摘要。当前项目中有用："
            "它记录 input_material_count、deduped_material_count、removed_duplicate_count、exact_duplicate_removed、high_overlap_removed、"
            "dropped_material_count、structured_evidence_count、merged_evidence_count、output_evidence_count、llm_invalid_output_count、"
            "upstream_acquisition_status、upstream_dropped_item_count、short_circuit_reason 等。"
            "该字段用于解释处理过程和排查问题，不承载 evidence 正文。"
        ),
    )
    processing_status: EvidenceProcessingStatus = Field(
        description=(
            "必填字段。Evidence Processing 阶段自身的处理状态。当前项目中有用：Research Executor 可用它判断当前轮 evidence 是否可继续交给后续阶段。"
            "可选值包括 success、partial_success、no_result、failed。success 表示成功产出 evidence 且没有明显处理降级；"
            "partial_success 表示产出了 evidence 但部分 material 结构化失败或被丢弃；no_result 表示未产出 evidence，可能因为上游 no_result/failed、"
            "normalized_items 为空或全部材料被过滤；failed 表示 EvidenceProcessingService 自身遇到未预期异常。"
            "它不同于 EvidenceProcessingRequest.acquisition_status：后者是上游 retrieval 获取状态，本字段是 evidence processing 处理结果。"
        ),
    )
    error_info: str | None = Field(
        default=None,
        description=(
            "可选字段。Evidence Processing 阶段的顶层错误或降级说明。当前项目中有用：processing_status='partial_success' 时，"
            "当前可能为 Some materials could not be structured；processing_status='failed' 时会保存异常的简短字符串；"
            "success/no_result 常为 None。该字段应保持简短，不承载完整 LLM 原始输出、完整 prompt、provider raw payload 或 stack trace；"
            "更细的计数和原因应查看 evidence_processing_summary。"
        ),
    )
