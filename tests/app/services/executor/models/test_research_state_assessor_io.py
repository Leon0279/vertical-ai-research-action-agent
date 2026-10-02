"""ResearchStateAssessor service-private I/O model tests."""

from app.domain.enums import FamilyName
from app.services.executor.models.evidence_coverage_entry import EvidenceCoverageEntry
from app.services.executor.models.llm_next_evidence_need_payload import (
    LLMNextEvidenceNeedPayload,
)
from app.services.executor.models.llm_research_assessment_payload import (
    LLMResearchAssessmentPayload,
)
from app.services.executor.models.llm_research_gap_payload import (
    LLMResearchGapPayload,
)
from app.services.executor.models.research_state_assessor_input import (
    ResearchStateAssessorInput,
)
from app.services.executor.models.research_state_assessor_output import (
    ResearchStateAssessorOutput,
)


def _coverage_map() -> dict[str, EvidenceCoverageEntry]:
    return {
        "objective": EvidenceCoverageEntry(
            target_type="objective",
            target_text="验证当前研究目标。",
            coverage_status="not_covered",
            coverage_summary="尚未完成评估。",
        )
    }


def _gap() -> LLMResearchGapPayload:
    return LLMResearchGapPayload(
        gap_scope="objective_level",
        gap_nature="missing",
        gap_severity="important",
        gap_summary="缺少直接证据。",
        gap_target="当前研究目标",
        gap_actionability="补充直接事实证据。",
    )


def _evidence_need() -> LLMNextEvidenceNeedPayload:
    return LLMNextEvidenceNeedPayload(
        need_scope="objective_level",
        need_target="当前研究目标",
        need_purpose="establish_coverage",
        desired_evidence_kind="direct_fact",
        freshness_requirement="normal",
        minimum_support_requirement="any_relevant_signal",
        need_summary="补充直接事实证据。",
        coverage_target_key="objective",
    )


def test_research_state_assessor_input_is_json_safe() -> None:
    assessor_input = ResearchStateAssessorInput(
        original_query="验证当前研究目标。",
        task_type="TOPIC_EXPLORATION",
        user_goal="验证当前研究目标。",
        task_framing=None,
        constraints=[],
        project_context_summary=None,
        current_bottleneck_summary=None,
        active_decision_summary=None,
        current_action_status=None,
        plan=[],
        sub_questions=[],
        comparison_candidates=[],
        initial_evidence_strategy=[],
        research_support=[],
        decision_support=[],
        action_support=[],
        iteration_index=1,
        remaining_iteration_budget=2,
        latency_budget_ms=None,
        available_families=[FamilyName.DOCS_SEARCH],
        processed_evidence_units=[],
        evidence_coverage_map=_coverage_map(),
        intermediate_findings=[],
        identified_gaps=[],
        top_gap=None,
        next_evidence_need=None,
        recent_retrieval_attempts=[],
    )

    dumped = assessor_input.model_dump(mode="json")

    assert dumped["available_families"] == ["docs_search"]
    assert dumped["evidence_coverage_map"]["objective"]["target_type"] == (
        "objective"
    )
    assert "stage_input" not in dumped
    assert "run_state" not in dumped


def test_research_state_assessor_output_keeps_typed_decision() -> None:
    gap = _gap()
    evidence_need = _evidence_need()
    output = ResearchStateAssessorOutput(
        assessment=LLMResearchAssessmentPayload(
            coverage_status="not_covered",
            support_strength="insufficient_support",
            finding_maturity="tentative",
            assessment_summary="当前缺少足够证据。",
        ),
        identified_gaps=[gap],
        top_gap=gap,
        next_evidence_need=evidence_need,
        evidence_coverage_map=_coverage_map(),
        prioritization_summary="优先补齐目标级直接证据。",
        action_mode="external_acquisition",
        preferred_family=FamilyName.DOCS_SEARCH,
        retrieval_query="当前研究目标 官方直接证据",
        action_rationale="当前需要补充官方直接证据。",
        acquisition_paths_exhausted=False,
    )

    dumped = output.model_dump(mode="json")

    assert output.top_gap is not None
    assert output.next_evidence_need.coverage_target_key == "objective"
    assert dumped["assessment"]["support_strength"] == "insufficient_support"
    assert dumped["evidence_coverage_map"]["objective"]["coverage_status"] == (
        "not_covered"
    )
    assert dumped["action_mode"] == "external_acquisition"
    assert dumped["preferred_family"] == "docs_search"
