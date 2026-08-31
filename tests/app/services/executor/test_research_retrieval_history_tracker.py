"""Research Executor 检索历史闭环测试。"""

from __future__ import annotations

import asyncio

from app.domain.enums import (
    AcquisitionStatus,
    FamilyName,
    RetrievalResultUtility,
)
from app.domain.models import (
    RecentRetrievalAttempt,
    ResearchStageInput,
    RetrievalAttemptTrace,
    RetrievalTrace,
    ToolExecutionLayerResult,
)
from app.services.executor.iteration_outcome_evaluator import IterationOutcomeEvaluator
from app.services.executor.models.evidence_coverage_entry import EvidenceCoverageEntry
from app.services.executor.models.research_executor_iteration_state import (
    ResearchExecutorIterationState,
)
from app.services.executor.models.research_executor_llm_payloads import (
    _LLMNextEvidenceNeedPayload,
    _LLMResearchAssessmentPayload,
    _LLMResearchGapPayload,
)
from app.services.executor.models.research_executor_run_state import (
    ResearchExecutorRunState,
)
from app.services.executor.research_action_decider import ResearchActionDecider
from app.services.executor.research_retrieval_history_tracker import (
    ResearchRetrievalHistoryTracker,
)


class _FailIfCalledLLMClient:
    async def generate_text(self, prompt: str) -> str:
        raise AssertionError(f"不应调用 outcome LLM：{prompt}")

    async def generate_json_object(self, prompt: str) -> dict[str, object]:
        raise AssertionError(f"不应调用 outcome LLM：{prompt}")


def _run_state(
    *,
    recent_retrieval_attempts: list[RecentRetrievalAttempt] | None = None,
) -> ResearchExecutorRunState:
    return ResearchExecutorRunState(
        evidence_coverage_map={
            "objective": EvidenceCoverageEntry(
                target_type="objective",
                target_text="验证当前研究目标。",
                coverage_status="not_covered",
                coverage_summary="尚未形成足够证据。",
            )
        },
        current_assessment=_LLMResearchAssessmentPayload(
            coverage_status="not_covered",
            support_strength="weak_support",
            finding_maturity="tentative",
            assessment_summary="当前缺少关键证据。",
        ),
        top_gap=_LLMResearchGapPayload(
            gap_scope="objective_level",
            gap_nature="weak",
            gap_severity="important",
            gap_summary="当前目标缺少可靠支撑。",
        ),
        next_evidence_need=_LLMNextEvidenceNeedPayload(
            need_scope="objective_level",
            need_purpose="establish_coverage",
            desired_evidence_kind="stronger_supporting_evidence",
            freshness_requirement="normal",
            minimum_support_requirement="any_relevant_signal",
            need_summary="补齐当前目标的可靠支撑材料。",
            coverage_target_key="objective",
        ),
        recent_retrieval_attempts=list(recent_retrieval_attempts or []),
        current_iteration=ResearchExecutorIterationState(
            iteration_index=1,
            remaining_iteration_budget=2,
        ),
    )


def _attempt(
    family: FamilyName,
    *,
    status: AcquisitionStatus = AcquisitionStatus.NO_RESULT,
    utility: RetrievalResultUtility = RetrievalResultUtility.NOT_USEFUL,
    target_key: str = "objective",
) -> RecentRetrievalAttempt:
    return RecentRetrievalAttempt(
        coverage_target_key=target_key,
        selected_family=family,
        selected_tool=f"{family.value}_tool",
        target_problem="补齐当前目标的可靠支撑材料。",
        generated_query=f"{family.value} query",
        query_fingerprint=f"{family.value} query",
        result_status=status,
        result_utility=utility,
    )


def test_history_tracker_records_attempt_after_outcome_and_bounds_history() -> None:
    tracker = ResearchRetrievalHistoryTracker()
    old_attempts = [
        _attempt(
            FamilyName.DOCS_SEARCH,
            status=AcquisitionStatus.SUCCESS,
            utility=RetrievalResultUtility.WEAKLY_USEFUL,
            target_key=f"old:{index}",
        )
        for index in range(8)
    ]
    state = _run_state(recent_retrieval_attempts=old_attempts)
    iteration = state.require_current_iteration()
    iteration.tool_execution_result = ToolExecutionLayerResult(
        execution_status="completed",
        acquisition_status=AcquisitionStatus.NO_RESULT,
        retrieval_trace=RetrievalTrace(
            target_problem="补齐当前目标的可靠支撑材料。",
            selected_family=FamilyName.RESEARCH_KNOWLEDGE_RECALL,
            selected_tool="research_knowledge_memory_v1",
            attempts=[
                RetrievalAttemptTrace(
                    selected_family=FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                    selected_tool="research_knowledge_memory_v1",
                    generated_query="memory retrieval query",
                    acquisition_status=AcquisitionStatus.NO_RESULT,
                )
            ],
        ),
    )

    tracker.record_completed_iteration(state)

    assert len(state.recent_retrieval_attempts) == 8
    recorded_attempt = state.recent_retrieval_attempts[-1]
    assert recorded_attempt.coverage_target_key == "objective"
    assert recorded_attempt.selected_family == FamilyName.RESEARCH_KNOWLEDGE_RECALL
    assert recorded_attempt.selected_tool == "research_knowledge_memory_v1"
    assert recorded_attempt.result_utility == RetrievalResultUtility.NOT_USEFUL
    prompt_history = tracker.assessment_prompt_value(state)
    assert prompt_history[-1]["query_fingerprint"] == "8faf947b1cee1409"
    assert "generated_query" not in prompt_history[-1]


def test_memory_low_value_history_switches_current_target_to_external() -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _run_state(
        recent_retrieval_attempts=[
            _attempt(FamilyName.RESEARCH_KNOWLEDGE_RECALL),
        ]
    )
    decider = ResearchActionDecider(retrieval_history_tracker=tracker)

    should_acquire = asyncio.run(
        decider.decide(
            ResearchStageInput(
                original_query="补齐当前目标的可靠支撑材料。",
                available_families=[FamilyName.RESEARCH_KNOWLEDGE_RECALL, FamilyName.DOCS_SEARCH],
            ),
            state,
        )
    )

    iteration = state.require_current_iteration()
    assert should_acquire is True
    assert iteration.action_mode == "external_acquisition"
    assert iteration.action_request is not None
    assert iteration.action_request.allowed_source_families == [
        FamilyName.DOCS_SEARCH
    ]


def test_weakly_useful_history_does_not_block_memory_path() -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _run_state(
        recent_retrieval_attempts=[
            _attempt(
                FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                status=AcquisitionStatus.SUCCESS,
                utility=RetrievalResultUtility.WEAKLY_USEFUL,
            )
        ]
    )
    decider = ResearchActionDecider(retrieval_history_tracker=tracker)

    should_acquire = asyncio.run(
        decider.decide(
            ResearchStageInput(
                original_query="补齐当前目标的可靠支撑材料。",
                available_families=[FamilyName.RESEARCH_KNOWLEDGE_RECALL, FamilyName.DOCS_SEARCH],
            ),
            state,
        )
    )

    assert should_acquire is True
    assert state.require_current_iteration().action_mode == "memory_backed_acquisition"


def test_exhausted_memory_and_external_paths_degrade_without_outcome_llm() -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _run_state(
        recent_retrieval_attempts=[
            _attempt(FamilyName.RESEARCH_KNOWLEDGE_RECALL),
            _attempt(FamilyName.DOCS_SEARCH),
        ]
    )
    decider = ResearchActionDecider(retrieval_history_tracker=tracker)

    should_acquire = asyncio.run(
        decider.decide(
            ResearchStageInput(
                original_query="补齐当前目标的可靠支撑材料。",
                available_families=[FamilyName.RESEARCH_KNOWLEDGE_RECALL, FamilyName.DOCS_SEARCH],
            ),
            state,
        )
    )
    outcome = asyncio.run(
        IterationOutcomeEvaluator(llm_client=_FailIfCalledLLMClient()).evaluate(
            ResearchStageInput(
                original_query="补齐当前目标的可靠支撑材料。",
                available_families=[FamilyName.RESEARCH_KNOWLEDGE_RECALL, FamilyName.DOCS_SEARCH],
            ),
            state,
        )
    )

    iteration = state.require_current_iteration()
    assert should_acquire is False
    assert iteration.acquisition_paths_exhausted is True
    assert outcome == "degrade"
    assert iteration.outcome_decision_source == "rule_short_circuit"
