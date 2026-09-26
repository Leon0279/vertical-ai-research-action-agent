"""ResearchStateAssessor 的强类型输出边界。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.services.executor.models.evidence_coverage_entry import EvidenceCoverageMap
from app.services.executor.models.research_executor_llm_payloads import (
    _LLMNextEvidenceNeedPayload,
    _LLMResearchAssessmentPayload,
    _LLMResearchGapPayload,
)


class ResearchStateAssessorOutput(BaseModel):
    """ResearchStateAssessor 校验完成后交还给 Research Executor 的完整结果。"""

    model_config = ConfigDict(extra="forbid")

    assessment: _LLMResearchAssessmentPayload = Field(
        description="必填字段。LLM 对当前研究 coverage、support 和 finding maturity 的判断。",
    )
    identified_gaps: list[_LLMResearchGapPayload] = Field(
        description="必填字段。本轮识别出的全部 research gaps。",
    )
    top_gap: _LLMResearchGapPayload = Field(
        description="必填字段。本轮选定的最高优先级 gap。",
    )
    next_evidence_need: _LLMNextEvidenceNeedPayload = Field(
        description="必填字段。由 top gap 推导出的下一项 evidence need。",
    )
    evidence_coverage_map: EvidenceCoverageMap = Field(
        description="必填字段。经过 target 和 evidence key 严格校验的全量 coverage map。",
    )
    prioritization_summary: str = Field(
        min_length=1,
        description="必填字段。选择 top gap 与 next evidence need 的简短优先级说明。",
    )
