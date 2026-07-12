"""Processed evidence unit 领域模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.domain.enums import FamilyName
from app.domain.models.source import SourceReference

EvidenceType = Literal[
    "direct_fact",
    "supporting_signal",
    "comparison_signal",
    "status_signal",
    "background_signal",
]


class ProcessedEvidenceUnit(BaseModel):
    """Evidence Processing 阶段产出的单条结构化 evidence。

    该模型由 EvidenceProcessingService 从 normalized retrieval material 转换而来，面向后续
    Research Executor / finding / synthesis / conclusion 阶段。它表达的是“某条内容可以作为当前任务的
    evidence signal”，不是最终结论，也不负责 memory write-back。
    """

    evidence_unit_id: str = Field(
        description=(
            "必填字段。当前 EvidenceProcessingResult 内稳定的 evidence unit ID。当前项目中有用："
            "EvidenceProcessingService 会先用 pending 创建 unit，最后通过 _assign_evidence_ids(...) 赋值为 ev_001、ev_002 等。"
            "该 ID 只保证在本次 processing result 内稳定，不表示数据库主键，也不表示跨轮长期 evidence ID。"
        ),
    )
    source_references: list[SourceReference] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。该 evidence unit 的唯一正式 provenance 字段。当前项目中有用："
            "EvidenceProcessingService 会从 NormalizedRetrievalItem.source_references 原样透传到这里，"
            "用于保留 URL、稳定 ID、ID 类型、标题、作者、publisher、发布时间、evidence span、metadata 等结构化来源信息。"
            "第一个 SourceReference 通常是 primary source reference；如果调用方需要轻量字符串引用，应从该字段按需派生，"
            "而不是依赖额外的 source_ref 或 support_refs 字段。"
            "单来源 material 通常只有 1 个 SourceReference；research_knowledge_recall 等场景可能包含多个 distill 前原始来源。"
        ),
    )
    source_family: FamilyName | None = Field(
        default=None,
        description=(
            "可选字段，默认 None。该 evidence 来源 material 所属的 retrieval family。当前项目中有用："
            "通常来自 NormalizedRetrievalItem.source_family；如果 material 缺失，则会从 retrieval_trace.selected_family "
            "或 source_summary.selected_family 派生。典型值包括 docs_search、web_search、paper_search、research_knowledge_recall。"
            "该字段用于 evidence coverage summary 和后续按 family 分析 evidence 来源。它不同于 source type："
            "原始来源类型不再作为 ProcessedEvidenceUnit 的独立字段暴露，应从 source_references[*].source_type 读取。"
        ),
    )
    content: str = Field(
        min_length=1,
        description=(
            "必填字段，不能为空字符串。面向当前任务整理后的 evidence 内容。当前项目中有用："
            "如果未注入 LLM client，deterministic fallback 会直接使用 material.content；如果注入 LLM client，"
            "则来自 LLM 结构化输出的 evidence_units[*].content。该字段应只包含 source-grounded 内容，"
            "不应包含最终结论、建议、行动计划或额外推理过程。"
        ),
    )
    evidence_type: EvidenceType = Field(
        description=(
            "必填字段。该 evidence 的信号类型。当前项目中有用：后续 synthesis / finding 阶段可用它区分事实、"
            "背景、状态、对比等不同 evidence。可选值包括 direct_fact、supporting_signal、comparison_signal、"
            "status_signal、background_signal。deterministic fallback 当前默认生成 supporting_signal。"
        ),
    )
    target_problem: str | None = Field(
        default=None,
        description=(
            "可选字段。该 evidence 对应的上游目标问题。当前项目中有用：EvidenceProcessingService 会从 "
            "retrieval_trace['target_problem'] 读取并写入这里，用于让后续阶段知道这条 evidence 服务于哪个 retrieval intent。"
            "如果上游 trace 未提供，则为 None。"
        ),
    )
    target_scope: dict[str, Any] | None = Field(
        default=None,
        description=(
            "可选字段。该 evidence 对应的目标范围约束。当前项目中暂未稳定使用，但保留给上游 retrieval context 透传。"
            "EvidenceProcessingService 当前只会在 retrieval_trace['target_scope'] 是 dict 时写入。"
            "该 dict 当前没有强 schema；可能包含后续任务范围、实体范围、时间范围、project/user scope 等结构化约束。"
            "如果没有明确范围信息，则为 None。"
        ),
    )
    evidence_goal: str | None = Field(
        default=None,
        description=(
            "可选字段。该 evidence 服务的 evidence goal。当前项目中有用：EvidenceProcessingService 会从 "
            "retrieval_trace['evidence_goal'] 读取并写入这里，用于解释这条 evidence 是为了支持覆盖、对比、状态确认、"
            "背景补充还是其它目标。没有该信息时为 None。"
        ),
    )
    sub_question: str | None = Field(
        default=None,
        description=(
            "可选字段。该 evidence 对应的子问题标签。当前项目中暂未大规模使用，但对未来 decomposition / research executor "
            "很有用：同一轮 retrieval 可能服务于一个大问题下的多个 sub-question。EvidenceProcessingService 当前从 "
            "retrieval_trace['sub_question'] 读取；没有该信息时为 None。"
        ),
    )
    comparison_candidate: str | None = Field(
        default=None,
        description=(
            "可选字段。该 evidence 关联的比较候选对象。当前项目中有用但不是所有任务都会填写："
            "在 comparison_evidence / paper_search 等场景中，可用于标记这条 evidence 支持哪个候选方法、工具、方案或实体。"
            "EvidenceProcessingService 当前从 retrieval_trace['comparison_candidate'] 读取；没有该信息时为 None。"
        ),
    )
    gap: str | None = Field(
        default=None,
        description=(
            "可选字段。该 evidence 对应的信息缺口标签。当前项目中暂未稳定使用，但对未来 research planning / gap filling "
            "有用：可标记这条 evidence 是为了填补哪个已识别的信息缺口。EvidenceProcessingService 当前从 "
            "retrieval_trace['gap'] 读取；没有该信息时为 None。"
        ),
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "可选字段，默认空 dict。该 evidence unit 的处理过程和 provenance 扩展信息。当前项目中有用："
            "EvidenceProcessingService 当前会写入 structuring_method（取值通常为 deterministic_fallback 或 llm）、"
            "item_id（原始 NormalizedRetrievalItem.item_id）、selected_tool（从 retrieval_trace 或 source_summary 派生）、"
            "generated_query（从 retrieval_trace 派生）。"
            "当 evidence consolidation 合并 unit 时，还会写入 consolidated=True。"
            "该 dict 用于补充处理/调试信息，不应长期承载已经稳定建模的主字段；正式来源对象应优先读取 source_references。"
        ),
    )
