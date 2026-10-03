"""ResearchStateAssessor typed boundary tests."""

import asyncio
import logging
from copy import deepcopy
from typing import Any

import pytest

from app.domain.enums import (
    AcquisitionStatus,
    FamilyName,
    RetrievalResultUtility,
)
from app.domain.models import RecentRetrievalAttempt
from app.services.executor.models.evidence_coverage_entry import (
    EvidenceCoverageEntry,
)
from app.services.executor.models.research_state_assessor_input import (
    ResearchStateAssessorInput,
)
from app.services.executor.models.research_state_assessor_output import (
    ResearchStateAssessorOutput,
)
from app.services.executor.research_coverage_tracker import ResearchCoverageTracker
from app.services.executor.research_retrieval_history_tracker import (
    ResearchRetrievalHistoryTracker,
)
from app.services.executor.research_state_assessor import ResearchStateAssessor


class _FakeLLMClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.prompts: list[str] = []

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        return deepcopy(self._response)


def _assessor_input() -> ResearchStateAssessorInput:
    return ResearchStateAssessorInput(
        original_query="评估当前研究目标。",
        task_type="TOPIC_EXPLORATION",
        user_goal="评估当前研究目标。",
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
        evidence_coverage_map={
            "objective": EvidenceCoverageEntry(
                target_type="objective",
                target_text="评估当前研究目标。",
                coverage_status="not_covered",
                coverage_summary="尚未完成评估。",
            )
        },
        intermediate_findings=[],
        identified_gaps=[],
        top_gap=None,
        next_evidence_need=None,
        recent_retrieval_attempts=[],
    )


def _valid_response() -> dict[str, Any]:
    gap = {
        "gap_scope": "objective_level",
        "gap_nature": "missing",
        "gap_severity": "important",
        "gap_summary": "缺少直接证据。",
        "gap_target": "当前研究目标",
        "gap_actionability": "补充直接事实证据。",
    }
    return {
        "assessment": {
            "coverage_status": "not_covered",
            "support_strength": "insufficient_support",
            "finding_maturity": "tentative",
            "assessment_summary": "当前缺少足够证据。",
        },
        "identified_gaps": [gap],
        "top_gap": gap,
        "next_evidence_need": {
            "need_scope": "objective_level",
            "need_target": "当前研究目标",
            "need_purpose": "establish_coverage",
            "desired_evidence_kind": "direct_fact",
            "freshness_requirement": "normal",
            "minimum_support_requirement": "any_relevant_signal",
            "need_summary": "补充直接事实证据。",
            "coverage_target_key": "objective",
        },
        "evidence_coverage_snapshot": [
            {
                "target_key": "objective",
                "coverage_status": "not_covered",
                "supporting_evidence_keys": [],
                "uncovered_aspects": ["缺少直接证据。"],
                "coverage_summary": "当前研究目标尚未获得直接证据。",
            }
        ],
        "prioritization_summary": "优先补充目标级直接证据。",
        "action_mode": "external_acquisition",
        "preferred_family": "docs_search",
        "retrieval_query": "当前研究目标 官方直接证据",
        "action_rationale": "当前需要官方直接证据。",
    }


def test_assess_returns_typed_output_without_mutating_input_snapshot(caplog) -> None:
    caplog.set_level(
        logging.INFO,
        logger="app.services.executor.research_state_assessor",
    )
    llm_client = _FakeLLMClient(_valid_response())
    assessor = ResearchStateAssessor(
        llm_client=llm_client,
        coverage_tracker=ResearchCoverageTracker(),
        retrieval_history_tracker=ResearchRetrievalHistoryTracker(),
    )
    assessor_input = _assessor_input()
    input_before_assessment = assessor_input.model_dump(mode="json")

    output = asyncio.run(assessor.assess(assessor_input))

    assert isinstance(output, ResearchStateAssessorOutput)
    assert output.assessment.coverage_status == "not_covered"
    assert output.top_gap.gap_summary == "缺少直接证据。"
    assert output.next_evidence_need.coverage_target_key == "objective"
    assert output.action_mode == "external_acquisition"
    assert output.preferred_family == FamilyName.DOCS_SEARCH
    assert output.retrieval_query == "当前研究目标 官方直接证据"
    assert output.evidence_coverage_map["objective"].target_text == (
        "评估当前研究目标。"
    )
    assert assessor_input.model_dump(mode="json") == input_before_assessment
    assert len(llm_client.prompts) == 1
    assessment_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "research_state_assessed"
    )
    assert assessment_record.generated_query == "当前研究目标 官方直接证据"
    assert len(assessment_record.query_fingerprint) == 16


@pytest.mark.parametrize(
    ("action_mode", "preferred_family", "retrieval_query"),
    [
        ("refine_from_existing_state", None, None),
        (
            "memory_backed_acquisition",
            FamilyName.RESEARCH_KNOWLEDGE_RECALL,
            "当前研究目标 已有知识",
        ),
        (
            "external_acquisition",
            FamilyName.DOCS_SEARCH,
            "当前研究目标 官方直接证据",
        ),
    ],
)
def test_assess_accepts_each_consistent_action_contract(
    action_mode: str,
    preferred_family: FamilyName | None,
    retrieval_query: str | None,
) -> None:
    response = _valid_response()
    response.update(
        action_mode=action_mode,
        preferred_family=preferred_family,
        retrieval_query=retrieval_query,
    )
    available_families = (
        [preferred_family]
        if preferred_family is not None
        else [FamilyName.DOCS_SEARCH]
    )
    assessor_input = _assessor_input().model_copy(
        update={"available_families": available_families}
    )
    assessor = ResearchStateAssessor(
        llm_client=_FakeLLMClient(response),
        coverage_tracker=ResearchCoverageTracker(),
        retrieval_history_tracker=ResearchRetrievalHistoryTracker(),
    )

    output = asyncio.run(assessor.assess(assessor_input))

    assert output.action_mode == action_mode
    assert output.preferred_family == preferred_family
    assert output.retrieval_query == retrieval_query


def test_assess_rejects_action_family_query_schema_mismatch() -> None:
    response = _valid_response()
    response["action_mode"] = "memory_backed_acquisition"
    response["preferred_family"] = "docs_search"
    assessor = ResearchStateAssessor(
        llm_client=_FakeLLMClient(response),
        coverage_tracker=ResearchCoverageTracker(),
        retrieval_history_tracker=ResearchRetrievalHistoryTracker(),
    )

    with pytest.raises(ValueError, match="required schema"):
        asyncio.run(assessor.assess(_assessor_input()))


def test_assess_rejects_unavailable_preferred_family() -> None:
    response = _valid_response()
    response["preferred_family"] = "web_search"
    assessor = ResearchStateAssessor(
        llm_client=_FakeLLMClient(response),
        coverage_tracker=ResearchCoverageTracker(),
        retrieval_history_tracker=ResearchRetrievalHistoryTracker(),
    )

    with pytest.raises(ValueError, match="not currently available"):
        asyncio.run(assessor.assess(_assessor_input()))


def test_assess_allows_family_with_low_value_history() -> None:
    assessor_input = _assessor_input().model_copy(
        update={
            "recent_retrieval_attempts": [
                RecentRetrievalAttempt(
                    coverage_target_key="objective",
                    selected_family=FamilyName.DOCS_SEARCH,
                    target_problem="评估当前研究目标。",
                    generated_query="旧的低价值 query",
                    query_fingerprint="old-query",
                    result_status=AcquisitionStatus.NO_RESULT,
                    result_utility=RetrievalResultUtility.NOT_USEFUL,
                )
            ]
        }
    )
    llm_client = _FakeLLMClient(_valid_response())
    assessor = ResearchStateAssessor(
        llm_client=llm_client,
        coverage_tracker=ResearchCoverageTracker(),
        retrieval_history_tracker=ResearchRetrievalHistoryTracker(),
    )

    output = asyncio.run(assessor.assess(assessor_input))

    assert output.preferred_family == FamilyName.DOCS_SEARCH
    prompt = llm_client.prompts[0]
    assert '"selected_family": "docs_search"' in prompt
    assert "此前效果不佳不会自动禁止再次选择同一 family 或 query" in prompt
    assert "建议避免在没有新理由时原样重复" in prompt


def test_assess_allows_repeated_low_value_query() -> None:
    response = _valid_response()
    assessor_input = _assessor_input().model_copy(
        update={
            "recent_retrieval_attempts": [
                RecentRetrievalAttempt(
                    coverage_target_key="objective",
                    selected_family=FamilyName.DOCS_SEARCH,
                    target_problem="评估当前研究目标。",
                    generated_query=response["retrieval_query"],
                    query_fingerprint="repeated-query",
                    result_status=AcquisitionStatus.FAILED,
                    result_utility=RetrievalResultUtility.NOT_USEFUL,
                )
            ]
        }
    )
    assessor = ResearchStateAssessor(
        llm_client=_FakeLLMClient(response),
        coverage_tracker=ResearchCoverageTracker(),
        retrieval_history_tracker=ResearchRetrievalHistoryTracker(),
    )

    output = asyncio.run(assessor.assess(assessor_input))

    assert output.retrieval_query == response["retrieval_query"]


def test_assess_allows_refine_when_current_target_paths_are_low_value() -> None:
    response = _valid_response()
    response.update(
        action_mode="refine_from_existing_state",
        preferred_family=None,
        retrieval_query=None,
    )
    assessor_input = _assessor_input().model_copy(
        update={
            "recent_retrieval_attempts": [
                RecentRetrievalAttempt(
                    coverage_target_key="objective",
                    selected_family=FamilyName.DOCS_SEARCH,
                    target_problem="评估当前研究目标。",
                    generated_query="旧的低价值 query",
                    query_fingerprint="old-query",
                    result_status=AcquisitionStatus.NO_RESULT,
                    result_utility=RetrievalResultUtility.NOT_USEFUL,
                )
            ]
        }
    )
    assessor = ResearchStateAssessor(
        llm_client=_FakeLLMClient(response),
        coverage_tracker=ResearchCoverageTracker(),
        retrieval_history_tracker=ResearchRetrievalHistoryTracker(),
    )

    output = asyncio.run(assessor.assess(assessor_input))

    assert output.action_mode == "refine_from_existing_state"
    assert output.preferred_family is None
    assert output.retrieval_query is None
