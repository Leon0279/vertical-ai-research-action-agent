"""ResearchStateAssessor typed boundary tests."""

import asyncio
from copy import deepcopy
from typing import Any

from app.domain.enums import FamilyName
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
    }


def test_assess_returns_typed_output_without_mutating_input_snapshot() -> None:
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
    assert output.evidence_coverage_map["objective"].target_text == (
        "评估当前研究目标。"
    )
    assert assessor_input.model_dump(mode="json") == input_before_assessment
    assert len(llm_client.prompts) == 1
