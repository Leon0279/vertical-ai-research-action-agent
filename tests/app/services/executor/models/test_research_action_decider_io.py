"""ResearchActionDecider service-private I/O model tests."""

import pytest
from pydantic import ValidationError

from app.domain.enums import FamilyName
from app.services.executor.models.research_action_decider_input import (
    ResearchActionDeciderInput,
)
from app.services.executor.models.research_action_decider_output import (
    ResearchActionDeciderOutput,
)
from app.services.executor.models.research_action_request import ResearchActionRequest
from app.services.executor.models.llm_next_evidence_need_payload import (
    LLMNextEvidenceNeedPayload,
)
from app.services.executor.models.llm_research_assessment_payload import (
    LLMResearchAssessmentPayload,
)
from app.services.executor.models.llm_research_gap_payload import (
    LLMResearchGapPayload,
)


def _decider_input() -> ResearchActionDeciderInput:
    return ResearchActionDeciderInput(
        original_query="补齐当前研究目标的证据。",
        user_goal="验证当前研究目标。",
        available_families=[
            FamilyName.RESEARCH_KNOWLEDGE_RECALL,
            FamilyName.DOCS_SEARCH,
        ],
        latency_budget_ms=None,
        scope_restrictions=[],
        current_assessment=LLMResearchAssessmentPayload(
            coverage_status="not_covered",
            support_strength="weak_support",
            finding_maturity="tentative",
            assessment_summary="当前缺少关键证据。",
        ),
        top_gap=LLMResearchGapPayload(
            gap_scope="objective_level",
            gap_nature="missing",
            gap_severity="important",
            gap_summary="缺少直接证据。",
        ),
        next_evidence_need=LLMNextEvidenceNeedPayload(
            need_scope="objective_level",
            need_purpose="establish_coverage",
            desired_evidence_kind="direct_fact",
            freshness_requirement="normal",
            minimum_support_requirement="any_relevant_signal",
            need_summary="补充直接事实证据。",
            coverage_target_key="objective",
        ),
        recent_retrieval_attempts=[],
        iteration_index=1,
        remaining_iteration_budget=2,
    )


def test_research_action_decider_input_is_json_safe_and_forbids_extra_fields() -> None:
    decider_input = _decider_input()

    dumped = decider_input.model_dump(mode="json")

    assert dumped["available_families"] == [
        "research_knowledge_recall",
        "docs_search",
    ]
    assert dumped["current_assessment"]["coverage_status"] == "not_covered"
    with pytest.raises(ValidationError):
        ResearchActionDeciderInput.model_validate(
            {**dumped, "unexpected_field": True}
        )


def test_research_action_decider_output_is_json_safe_and_forbids_extra_fields() -> None:
    output = ResearchActionDeciderOutput(
        candidate_action_modes=[
            "refine_from_existing_state",
            "external_acquisition",
        ],
        action_mode="external_acquisition",
        action_decision_reason="external_only_candidate",
        action_rationale="当前只有 external 路径满足约束。",
        acquisition_paths_exhausted=False,
        action_request=ResearchActionRequest(
            action_mode="external_acquisition",
            target_problem="补充直接事实证据。",
            allowed_source_families=[FamilyName.DOCS_SEARCH],
            fallback_policy="fallback_to_broader_search",
        ),
    )

    dumped = output.model_dump(mode="json")

    assert dumped["action_request"]["allowed_source_families"] == [
        "docs_search"
    ]
    assert dumped["action_request"]["fallback_policy"] == (
        "fallback_to_broader_search"
    )
    with pytest.raises(ValidationError):
        ResearchActionDeciderOutput.model_validate(
            {**dumped, "unexpected_field": True}
        )
