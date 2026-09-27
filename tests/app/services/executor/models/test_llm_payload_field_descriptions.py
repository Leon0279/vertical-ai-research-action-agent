"""Research Executor LLM payload 字段说明测试。"""

from typing import Any, get_args

import pytest
from pydantic import BaseModel

from app.services.executor.models.llm_evidence_coverage_entry_payload import (
    LLMEvidenceCoverageEntryPayload,
)
from app.services.executor.models.llm_intermediate_findings_payload import (
    LLMIntermediateFindingsPayload,
)
from app.services.executor.models.llm_iteration_outcome_payload import (
    LLMIterationOutcomePayload,
)
from app.services.executor.models.llm_next_evidence_need_payload import (
    LLMNextEvidenceNeedPayload,
)
from app.services.executor.models.llm_research_assessment_and_gaps_payload import (
    LLMResearchAssessmentAndGapsPayload,
)
from app.services.executor.models.llm_research_assessment_payload import (
    LLMResearchAssessmentPayload,
)
from app.services.executor.models.llm_research_gap_payload import (
    LLMResearchGapPayload,
)


PAYLOAD_MODELS: tuple[type[BaseModel], ...] = (
    LLMResearchAssessmentPayload,
    LLMResearchGapPayload,
    LLMNextEvidenceNeedPayload,
    LLMEvidenceCoverageEntryPayload,
    LLMResearchAssessmentAndGapsPayload,
    LLMIntermediateFindingsPayload,
    LLMIterationOutcomePayload,
)


@pytest.mark.parametrize("model", PAYLOAD_MODELS)
def test_every_llm_payload_field_description_contains_an_example(
    model: type[BaseModel],
) -> None:
    for field_name, field_info in model.model_fields.items():
        qualified_name = f"{model.__name__}.{field_name}"
        assert field_info.description is not None, f"{qualified_name} 缺少字段说明"
        assert "例如：" in field_info.description, f"{qualified_name} 缺少字段示例"


@pytest.mark.parametrize(
    ("model", "field_name", "example"),
    (
        (LLMResearchAssessmentPayload, "coverage_status", "partially_covered"),
        (LLMResearchAssessmentPayload, "support_strength", "moderate_support"),
        (LLMResearchAssessmentPayload, "finding_maturity", "partially_stable"),
        (LLMResearchGapPayload, "gap_scope", "sub_question_level"),
        (LLMResearchGapPayload, "gap_nature", "weak"),
        (LLMResearchGapPayload, "gap_severity", "important"),
        (LLMNextEvidenceNeedPayload, "need_scope", "sub_question_level"),
        (LLMNextEvidenceNeedPayload, "need_purpose", "strengthen_support"),
        (
            LLMNextEvidenceNeedPayload,
            "desired_evidence_kind",
            "stronger_supporting_evidence",
        ),
        (LLMNextEvidenceNeedPayload, "freshness_requirement", "fresh_preferred"),
        (
            LLMNextEvidenceNeedPayload,
            "minimum_support_requirement",
            "moderate_support",
        ),
        (LLMEvidenceCoverageEntryPayload, "coverage_status", "partially_covered"),
        (LLMIterationOutcomePayload, "top_gap_progress", "partially_advanced"),
        (LLMIterationOutcomePayload, "evidence_gain", "meaningful_gain"),
        (
            LLMIterationOutcomePayload,
            "finding_progress",
            "improved_but_not_stable",
        ),
        (LLMIterationOutcomePayload, "residual_uncertainty", "moderate"),
        (LLMIterationOutcomePayload, "proposed_iteration_outcome", "continue"),
    ),
)
def test_enum_field_description_uses_a_legal_example(
    model: type[BaseModel],
    field_name: str,
    example: str,
) -> None:
    field_info: Any = model.model_fields[field_name]

    assert example in get_args(field_info.annotation)
    assert f"例如：{example}" in field_info.description
