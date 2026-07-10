"""Processed evidence 输出的 typed summary。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProcessedEvidenceSummary(BaseModel):
    """当前轮 processed evidence units 的轻量结果摘要。

    该模型用于快速描述 EvidenceProcessingResult.processed_evidence_units 的规模、类型分布和来源覆盖。
    它不是 evidence 正文本身，也不承载 final conclusion。
    """

    new_evidence_count: int = Field(
        default=0,
        ge=0,
        description=(
            "可选字段，默认 0，必须大于等于 0。当前轮最终输出的 ProcessedEvidenceUnit 数量。"
            "当前项目中有用：Research Executor 或后续 synthesis 阶段可用它快速判断本轮 evidence 是否有新增。"
            "该值应等于 processed_evidence_units 的长度。"
        ),
    )
    evidence_type_breakdown: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。按 evidence_type 统计当前轮 evidence 数量。当前项目中有用："
            "EvidenceProcessingService 当前会按 ProcessedEvidenceUnit.evidence_type 写入计数。"
            "当前可能包含的 key 来自 EvidenceType：direct_fact、supporting_signal、comparison_signal、status_signal、background_signal；"
            "value 是对应 evidence_type 的数量，必须是非负整数。"
        ),
    )
    source_coverage_summary: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。当前轮 evidence 覆盖的来源维度摘要。当前项目中有用：EvidenceProcessingService 当前写入 "
            "source_families 和 source_types 两个 key。source_families 是去重后的 retrieval family 名称列表，例如 docs_search、web_search、"
            "paper_search、research_knowledge_recall；source_types 是去重后的原始来源类型列表，例如 document、web_page、paper、run_output、conversation。"
            "该 dict 只做覆盖摘要，不替代每个 evidence unit 的 source_ref/support_refs。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。processed evidence summary 的扩展信息。当前项目中暂未稳定写入 key，"
            "主要预留给后续 evidence-level 覆盖统计或诊断信息。不要把 new_evidence_count、evidence_type_breakdown、"
            "source_coverage_summary 这些已经稳定建模的主字段长期塞在这里。"
        ),
    )

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        return self.metadata.get(key, default)

    def __getitem__(self, key: str) -> Any:
        value = self.get(key, None)
        if value is None and key not in self.metadata and not hasattr(self, key):
            raise KeyError(key)
        return value
