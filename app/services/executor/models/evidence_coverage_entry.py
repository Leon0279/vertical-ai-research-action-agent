"""Research Executor 内部的 evidence coverage 状态模型。"""

from __future__ import annotations

from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

EvidenceCoverageStatus = Literal["covered", "partially_covered", "not_covered"]
EvidenceCoverageTargetType = Literal[
    "objective",
    "sub_question",
    "comparison_candidate",
]


class EvidenceCoverageEntry(BaseModel):
    """单个 coverage target 的 stage-local evidence coverage 状态。

    该模型仅服务于一次 `ResearchExecutorService.execute(...)` 调用期间的
    `evidence_coverage_map`。它不是 `ResearchStageResult`、`RunningState`、API
    或数据库 contract；进入 assessment LLM prompt 时由 Research Executor 显式
    序列化为 JSON-safe dict。
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_type: EvidenceCoverageTargetType = Field(
        description=(
            "必填字段。该 map entry 代表的受控研究对象类型。当前由 Research Executor "
            "根据 ResearchStageInput 的 objective、sub_questions 或 comparison_candidates "
            "确定；LLM 不得创建或修改该字段。"
        )
    )
    target_text: str = Field(
        min_length=1,
        description=(
            "必填字段。该 coverage target 的研究目标、子问题或比较候选项文本。当前由 "
            "Research Executor 从 ResearchStageInput 确定，用于让 assessment LLM 理解 "
            "map key 对应的研究对象；LLM 不得改写该字段。"
        ),
    )
    coverage_status: EvidenceCoverageStatus = Field(
        description=(
            "必填字段。该 target 当前的语义 evidence 覆盖状态。当前由 assessment LLM 的 "
            "全量 coverage snapshot 写入；系统不会因为刚取得候选材料而直接提升该状态。"
        )
    )
    retrieved_evidence_keys: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。系统为补齐该 target 而取得的候选 ProcessedEvidenceUnit "
            "稳定 key。当前仅由 Research Executor Step 6 确定性追加；它不表示这些材料已经 "
            "被确认支撑该 target。"
        ),
    )
    supporting_evidence_keys: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。assessment LLM 已确认实际支撑该 target 的 "
            "ProcessedEvidenceUnit 稳定 key。当前只能引用本次 working state 中已存在的 "
            "processed evidence；不能因为候选材料被取得而自动写入。"
        ),
    )
    uncovered_aspects: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。该 target 仍未覆盖、证据偏弱或需要补强的具体方面。当前由 "
            "assessment LLM 的全量 coverage snapshot 写入，供下一轮 gap 判断和 evidence need "
            "选择使用。"
        ),
    )
    coverage_summary: str = Field(
        min_length=1,
        description=(
            "必填字段。该 target 当前 coverage 状态的简短中文摘要。初始值由 Research Executor "
            "提供；后续由 assessment LLM 的全量 coverage snapshot 更新。"
        ),
    )


EvidenceCoverageMap: TypeAlias = dict[str, EvidenceCoverageEntry]
