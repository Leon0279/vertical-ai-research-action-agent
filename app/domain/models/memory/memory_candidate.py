"""Domain model for memory write-back candidates."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums.memory_type import MemoryType
from app.domain.models.memory.memory_candidate_details import (
    MemoryCandidateDetails,
    memory_candidate_details_match_type,
    parse_memory_candidate_details,
)
from app.domain.models.source import SourceReference


class MemoryCandidate(BaseModel):
    """当前 run 中可能值得写入长期 memory 的候选项。

    MemoryCandidate 表示 distillation 阶段的候选，不表示已经完成的数据库写入。
    因此它描述候选的语义、稳定性、范围和 provenance，但不承载 record_id、supersede
    关系或最终的 persistence action。
    """

    model_config = ConfigDict(extra="forbid")

    memory_type: MemoryType = Field(
        description=(
            "必填字段。该 candidate 建议写入的长期 memory 类型，例如 Decision Memory、"
            "Action / Execution Memory、Project Profile Memory 或 Research Knowledge Memory。"
            "当前由 MemoryDistillerService 根据 candidate 语义设置，MemoryPersistenceService 和"
            "下游 store 会据此决定目标 memory 层。它表示建议存放位置，不等同于 semantic_type。"
        ),
    )
    summary: str = Field(
        min_length=1,
        description=(
            "必填字段，不能为空字符串。该 candidate 的可持久化摘要。当前由 MemoryDistillerService"
            "从 final_recommendation、稳定 findings 或其它 durable signal 提炼，供 persistence layer"
            "写入 record。它应是简洁、可跨 session 复用的语义内容，不应是 raw transcript、raw tool payload"
            "或完整 LLM prompt。"
        ),
    )
    details: MemoryCandidateDetails = Field(
        description=(
            "必填字段。与 memory_type 严格对应的 typed business details。每种 details 只允许少量"
            "memory-type-specific 字段，所有字段均可省略；不得包含 record ID、dedupe、embedding、"
            "scope ownership、provenance、canonical/supersession 或 lifecycle 治理字段。"
        ),
    )
    confidence: float | None = Field(
        default=None,
        description=(
            "可选字段。系统对 candidate 内容可信度的数值信号，通常由当前 run 的最终 confidence"
            "映射得到。当前 MemoryDistillerService 会从 low/medium/high 映射为约 0.2/0.5/0.8，"
            "MemoryPersistenceService 会保留它供后续筛选或读取。它表示内容可信程度，不表示是否已经足够稳定可持久化。"
        ),
    )
    stability: str | None = Field(
        default=None,
        description=(
            "可选字段。candidate 是否已经稳定到适合跨 session 保留的信号，例如 tentative、stable。"
            "当前由 MemoryDistillerService 结合 confidence、caveats 和 open_questions 推导；"
            "它与 confidence 不同：confidence 表示当前内容有多可信，stability 表示是否已经适合成为 durable memory。"
        ),
    )
    project_scope_id: str | None = Field(
        default=None,
        description=(
            "可选字段。candidate 所属的项目范围标识。当前由 MemoryDistillerService 从"
            "RunningState.project_scope_id 透传，MemoryPersistenceService 将其写入持久化 payload，"
            "后续可用于 project-scoped 查询、隔离和权限判断。没有明确项目范围时为空。"
        ),
    )
    candidate_source: str = Field(
        default="run_output",
        description=(
            "可选字段，默认值为 run_output。candidate 的产生来源，例如 run_output、session_promotion。"
            "当前 MemoryDistillerService 对本次 run 产出的候选填写 run_output；该字段用于 provenance 和"
            "后续区分当前执行产物与 session promotion，不等同于 SourceReference.source_type。"
        ),
    )
    semantic_type: str | None = Field(
        default=None,
        description=(
            "可选字段。candidate 的语义类型，例如 stable_decision、project_state_update、"
            "action_state_update、reusable_research_knowledge。当前由 MemoryDistillerService 设置，"
            "用于区分 candidate 的本质语义；memory_type 则表示建议写入的 memory 分类。当前尚未固化为 enum。"
        ),
    )
    source_references: list[SourceReference] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。candidate 所依赖的原始 evidence 的 typed provenance 列表。"
            "当前 MemoryDistillerService 从 RunningState.retrieved_evidence_refs 透传，"
            "MemoryPersistenceService 会将其序列化为 JSON-safe dict list。它是 candidate 的 canonical 来源信息，"
            "不应退化为只保存 URL 的字符串列表。"
        ),
    )
    derived_from_run_id: str | None = Field(
        default=None,
        description=(
            "可选字段。candidate 来源的 run 标识。当前项目尚无独立 run_id 时，"
            "MemoryDistillerService 暂使用 RuntimeContext.request_id 填充；该字段用于审计、追踪和"
            "定位 candidate 的产生执行，不是 memory record 的最终 record_id。"
        ),
    )
    derived_from_session_id: str | None = Field(
        default=None,
        description=(
            "可选字段。candidate 来源的 session/thread 标识。当前由 MemoryDistillerService 从"
            "RuntimeContext.session_id 透传，便于区分 session provenance 和 long-term memory 本身的生命周期。"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def parse_details_for_memory_type(cls, value: Any) -> Any:
        """Select the details model from memory_type before union validation."""

        if not isinstance(value, dict):
            return value
        if "memory_type" not in value or "details" not in value:
            return value
        normalized = dict(value)
        normalized["details"] = parse_memory_candidate_details(
            normalized["memory_type"],
            normalized["details"],
        )
        return normalized

    @model_validator(mode="after")
    def validate_details_type(self) -> "MemoryCandidate":
        """Reject details that do not belong to this candidate's memory type."""

        if not memory_candidate_details_match_type(self.memory_type, self.details):
            raise ValueError("details model does not match memory_type")
        return self
