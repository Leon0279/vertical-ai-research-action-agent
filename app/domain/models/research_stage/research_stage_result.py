"""Research Stage 的显式输出模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models.source import SourceReference

ResearchStageStatus = Literal["completed", "partial_success", "no_result", "failed"]


class ResearchStageResult(BaseModel):
    """Research Executor 完成 research stage 后返回给 pipeline 的结果。

    ResearchStageResult 只包含 pipeline 可以安全回写到 RunningState 的最小结果字段。
    它不暴露 raw retrieval result、TEL 内部中间对象、完整 processed evidence list 或 final answer。
    """

    research_status: ResearchStageStatus = Field(
        default="no_result",
        description=(
            "可选字段，默认 no_result。Research Stage 的顶层执行状态。当前 scaffold 阶段默认不执行真实 "
            "research loop，因此默认返回 no_result。"
        ),
    )
    retrieved_evidence_refs: list[SourceReference] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。Research Stage 本轮采纳 evidence 对应的 typed 来源引用列表。"
            "当前项目中有用：pipeline 会将该字段原样去重追加到 RunningState.retrieved_evidence_refs。"
            "每个元素都是 SourceReference，可保留 source_type、source_id/source_id_type、source_url、title、"
            "authors、publisher、published_at、evidence_span 和 metadata 等 provenance 信息。该字段不保存 evidence 正文、"
            "raw TEL result 或完整 ProcessedEvidenceUnit；需要展示字符串引用时由调用方从 SourceReference 派生。"
        ),
    )
    evidence_summary: str | None = Field(
        default=None,
        description="可选字段。可回写到 RunningState.evidence_summary 的 research evidence 摘要。",
    )
    intermediate_findings: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。可追加到 RunningState.intermediate_findings 的中间发现。",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。可追加到 RunningState.open_questions 的未解决问题或降级原因。",
    )
    executed_iteration_count: int = Field(
        default=0,
        ge=0,
        description="可选字段，默认 0。Research Executor 实际执行的 research iteration 数量。",
    )
    error_info: str | None = Field(
        default=None,
        description="可选字段。Research Stage 顶层错误摘要；不应包含完整 stack trace 或 raw provider payload。",
    )
