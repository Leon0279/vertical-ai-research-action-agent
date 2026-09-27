"""LLM evidence coverage entry 的 service-private 输出模型。"""

from pydantic import BaseModel, ConfigDict, Field

from app.services.executor.enums import ResearchCoverageStatus


class LLMEvidenceCoverageEntryPayload(BaseModel):
    """表示 LLM 对单个 coverage target 的语义覆盖判断。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_key: str = Field(
        min_length=1,
        description=(
            "必填字段。必须逐字匹配输入 coverage_targets 中的 target_key。"
            "例如：sub_question:1。"
        ),
    )
    coverage_status: ResearchCoverageStatus = Field(
        description=(
            "必填字段。该 target 当前的 evidence 覆盖状态。"
            "例如：partially_covered。"
        ),
    )
    supporting_evidence_keys: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。经语义判断实际支撑该 target 的 "
            "evidence key；"
            "只能引用输入 processed_evidence。例如：[\"iteration_1:ev_001\"]。"
        ),
    )
    uncovered_aspects: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。该 target 仍未覆盖、偏弱或需要"
            "补强的方面。"
            "例如：[\"缺少公开的高并发基准测试数据\"]。"
        ),
    )
    coverage_summary: str = Field(
        min_length=1,
        description=(
            "必填字段。该 target 覆盖状态的简短中文说明。"
            "例如：官方文档确认支持并发处理，但性能上限仍未被覆盖。"
        ),
    )
