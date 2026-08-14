"""EvidenceProcessingService 的 typed processing summary。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidenceProcessingSummary(BaseModel):
    """Evidence Processing 阶段的处理计数和可观测摘要。

    该模型解释 EvidenceProcessingService 如何把 normalized materials 处理成 processed evidence units。
    它不承载 evidence 正文，也不表示最终答案。当前会出现在 EvidenceProcessingResult.evidence_processing_summary。
    """

    policy: str | None = Field(
        default=None,
        description=(
            "可选字段。Evidence Processing 使用的策略版本。当前项目中有用：EvidenceProcessingService 当前写入 "
            "evidence_processing_v1，用于后续排查处理行为是否来自同一版规则。"
        ),
    )
    input_material_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。进入 EvidenceProcessingService 的 normalized_items 数量。"
            "当前项目中有用：用于和 deduped_material_count、dropped_material_count、output_evidence_count 对照，判断材料在处理链路中的流失。"
        ),
    )
    deduped_material_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。dedup 后保留下来的 material 数量。当前项目中有用："
            "EvidenceProcessingService 会在 item_id exact duplicate、source_ref + content exact duplicate、same-source containment 去重后写入该值。"
        ),
    )
    removed_duplicate_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。dedup 阶段移除或合并的重复 material 总数。当前项目中有用："
            "该值等于 exact_duplicate_removed + high_overlap_removed。"
        ),
    )
    exact_duplicate_removed: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。exact duplicate 去重数量。当前项目中有用："
            "当两个 material 的 item_id 相同，或 primary source ref 相同且 normalized content 完全相同时，会计入该值。"
        ),
    )
    high_overlap_removed: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。same-source containment / high overlap 去重数量。当前项目中有用："
            "当两个 material 来自同一 primary source ref，且一个 normalized content 包含另一个时，会保留更长或 metadata 更多的 material，"
            "并把被覆盖的 material 计入该值。"
        ),
    )
    dropped_material_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。Evidence Processing 阶段丢弃的 material 数量。当前项目中有用："
            "质量不足、LLM structuring 异常、LLM decision=drop 或没有产出任何 evidence unit 的 material 都会计入该值。"
            "它不包含上游 TEL/family/tool 已经丢弃的 item；上游丢弃数量见 upstream_dropped_item_count。"
        ),
    )
    structured_evidence_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。consolidation 前初步结构化出的 evidence unit 数量。当前项目中有用："
            "如果未注入 LLM client，每条合格 material 会通过 deterministic fallback 生成 supporting_signal；如果注入 LLM，"
            "则来自 LLM JSON payload 中通过校验的 evidence_units。"
        ),
    )
    merged_evidence_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。evidence consolidation 阶段合并的 evidence unit 数量。当前项目中有用："
            "当同 evidence_type 的 exact/containment evidence 被保守合并时，会计入该值，并把 source_references 合并到 canonical unit。"
        ),
    )
    output_evidence_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。最终输出的 processed evidence unit 数量。当前项目中有用："
            "该值应等于 EvidenceProcessingResult.processed_evidence_units 的长度，也应等于 ProcessedEvidenceSummary.new_evidence_count。"
        ),
    )
    llm_invalid_output_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。LLM structuring 失败或输出不合法的 material 数量。当前项目中有用："
            "LLM 调用异常、非 JSON、schema 校验失败、字段为空等导致单条 material 无法结构化时会计入该值；"
            "单条 material 失败不会让整个 service 失败，但可能导致 processing_status='partial_success'。"
        ),
    )
    upstream_acquisition_status: str | None = Field(
        default=None,
        description=(
            "可选字段。上游 TEL 的 acquisition_status 字符串值。当前项目中有用：EvidenceProcessingService 会把 "
            "EvidenceProcessingRequest.acquisition_status 写入这里，用于解释 no_result / failed 短路或 partial_success 来源。"
        ),
    )
    upstream_dropped_item_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。上游 TEL/family/tool 在进入 Evidence Processing 前已经丢弃的 item 数量。"
            "当前项目中有用：用于和 dropped_material_count 区分不同阶段的丢弃。"
        ),
    )
    short_circuit_reason: str | None = Field(
        default=None,
        description=(
            "可选字段。EvidenceProcessingService 未进入完整 material processing 而直接返回空结果的原因。当前项目中有用："
            "当上游 acquisition_status 为 no_result/failed，或 normalized_items 为空时会写入简短原因；正常处理路径通常为 None。"
        ),
    )
    observability: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。Evidence Processing 阶段的扩展观测信息。当前项目中暂未稳定写入 key；"
            "兼容未来放置无法稳定建模但有诊断价值的信息。不要把 policy、各类 count、upstream_acquisition_status、"
            "short_circuit_reason 这些已经稳定建模的字段塞在这里。"
        ),
    )

    def get(self, key: str, default: Any = None) -> Any:
        """以兼容字典的方式读取正式摘要字段或 observability 扩展字段。

        Args:
            key (str): 需要读取的摘要字段或 observability 字段名称。
            default (Any): key 不存在时返回的默认值，默认是 None。

        Returns:
            Any: 已声明字段、observability 中对应的值，或找不到时的 default。
        """
        if hasattr(self, key):
            return getattr(self, key)
        return self.observability.get(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if value is None and key not in self.observability and not hasattr(self, key):
            raise KeyError(key)
        return value
