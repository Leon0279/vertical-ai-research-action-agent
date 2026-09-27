"""Research Executor 检索历史闭环测试。"""

from __future__ import annotations

import asyncio
import logging
from copy import deepcopy

import pytest

from app.domain.enums import (
    AcquisitionStatus,
    FamilyName,
    RetrievalResultUtility,
)
from app.domain.models import (
    EvidenceProcessingResult,
    ProcessedEvidenceUnit,
    RecentRetrievalAttempt,
    ResearchStageInput,
    RetrievalAttemptTrace,
    RetrievalTrace,
    ToolExecutionLayerResult,
)
from app.services.executor.iteration_outcome_evaluator import IterationOutcomeEvaluator
from app.services.executor.models.evidence_coverage_entry import EvidenceCoverageEntry
from app.services.executor.models.research_action_decider_input import (
    ResearchActionDeciderInput,
)
from app.services.executor.models.research_action_decider_output import (
    ResearchActionDeciderOutput,
)
from app.services.executor.models.research_executor_iteration_state import (
    ResearchExecutorIterationState,
)
from app.services.executor.models.llm_next_evidence_need_payload import (
    LLMNextEvidenceNeedPayload,
)
from app.services.executor.models.llm_research_assessment_payload import (
    LLMResearchAssessmentPayload,
)
from app.services.executor.models.llm_research_gap_payload import (
    LLMResearchGapPayload,
)
from app.services.executor.models.research_executor_run_state import (
    ResearchExecutorRunState,
)
from app.services.executor.models.research_iteration_evaluation_state import (
    ResearchIterationEvaluationState,
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
        current_assessment=LLMResearchAssessmentPayload(
            coverage_status="not_covered",
            support_strength="weak_support",
            finding_maturity="tentative",
            assessment_summary="当前缺少关键证据。",
        ),
        top_gap=LLMResearchGapPayload(
            gap_scope="objective_level",
            gap_nature="weak",
            gap_severity="important",
            gap_summary="当前目标缺少可靠支撑。",
        ),
        next_evidence_need=LLMNextEvidenceNeedPayload(
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


def _state_with_processed_evidence(
    *,
    top_gap_progress: str | None,
    evidence_gain: str | None,
) -> ResearchExecutorRunState:
    """构造已经产出 evidence、可用于派生 utility 的 iteration state。"""

    state = _run_state()
    iteration = state.require_current_iteration()
    evidence_unit = ProcessedEvidenceUnit(
        evidence_unit_id="ev_001",
        content="当前材料对 coverage target 提供了一条可评估的证据。",
        evidence_type="supporting_signal",
    )
    iteration.evidence_processing_result = EvidenceProcessingResult(
        processed_evidence_units=[evidence_unit],
        processing_status="success",
    )
    iteration.processed_evidence_units = [evidence_unit]
    if top_gap_progress is not None or evidence_gain is not None:
        iteration.evaluation_state = ResearchIterationEvaluationState(
            top_gap_progress=top_gap_progress,
            evidence_gain=evidence_gain,
        )
    return state


def _decider_input(
    stage_input: ResearchStageInput,
    state: ResearchExecutorRunState,
) -> ResearchActionDeciderInput:
    assessment = state.current_assessment
    top_gap = state.top_gap
    next_evidence_need = state.next_evidence_need
    assert assessment is not None
    assert top_gap is not None
    assert next_evidence_need is not None
    iteration = state.require_current_iteration()
    return ResearchActionDeciderInput(
        original_query=stage_input.original_query,
        user_goal=stage_input.user_goal,
        available_families=list(stage_input.available_families),
        latency_budget_ms=stage_input.latency_budget_ms,
        scope_restrictions=list(stage_input.scope_restrictions),
        current_assessment=assessment,
        top_gap=top_gap,
        next_evidence_need=next_evidence_need,
        recent_retrieval_attempts=list(state.recent_retrieval_attempts),
        iteration_index=iteration.iteration_index,
        remaining_iteration_budget=iteration.remaining_iteration_budget,
    )


def _apply_decider_output(
    state: ResearchExecutorRunState,
    output: ResearchActionDeciderOutput,
) -> None:
    iteration = state.require_current_iteration()
    iteration.candidate_action_modes = list(output.candidate_action_modes)
    iteration.action_mode = output.action_mode
    iteration.action_decision_reason = output.action_decision_reason
    iteration.action_rationale = output.action_rationale
    iteration.acquisition_paths_exhausted = output.acquisition_paths_exhausted
    iteration.action_request = output.action_request


def test_history_tracker_records_attempt_after_outcome_and_bounds_history(
    caplog,
) -> None:
    caplog.set_level(logging.INFO)
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
                ),
                RetrievalAttemptTrace(
                    selected_family=FamilyName.DOCS_SEARCH,
                    selected_tool="docs_search_v1",
                    generated_query="docs retrieval query",
                    acquisition_status=AcquisitionStatus.NO_RESULT,
                    fallback_applied=True,
                ),
            ],
        ),
    )

    tracker.record_completed_iteration(state)

    assert len(state.recent_retrieval_attempts) == 8
    recorded_attempt = state.recent_retrieval_attempts[-2]
    assert recorded_attempt.coverage_target_key == "objective"
    assert recorded_attempt.selected_family == FamilyName.RESEARCH_KNOWLEDGE_RECALL
    assert recorded_attempt.selected_tool == "research_knowledge_memory_v1"
    assert recorded_attempt.result_utility == RetrievalResultUtility.NOT_USEFUL
    assert state.recent_retrieval_attempts[-1].selected_family == FamilyName.DOCS_SEARCH
    prompt_history = tracker.assessment_prompt_value(
        state.recent_retrieval_attempts
    )
    assert prompt_history[-2]["query_fingerprint"] == "8faf947b1cee1409"
    assert "generated_query" not in prompt_history[-2]
    history_record = next(
        record
        for record in caplog.records
        if getattr(record, "event", None)
        == "research_retrieval_history_updated"
    )
    assert history_record.history_update_status == "updated"
    assert history_record.history_skip_reason is None
    assert history_record.coverage_target_key == "objective"
    assert history_record.new_retrieval_attempt_count == 2
    assert history_record.retrieval_history_count == 8
    assert history_record.retrieval_history_truncated_count == 2
    assert history_record.low_value_families == [
        FamilyName.DOCS_SEARCH,
        FamilyName.RESEARCH_KNOWLEDGE_RECALL,
    ]
    assert history_record.retrieval_attempts == [
        {
            "selected_family": FamilyName.RESEARCH_KNOWLEDGE_RECALL,
            "selected_tool": "research_knowledge_memory_v1",
            "query_fingerprint": "8faf947b1cee1409",
            "result_status": AcquisitionStatus.NO_RESULT,
            "result_utility": RetrievalResultUtility.NOT_USEFUL,
            "fallback_applied": False,
        },
        {
            "selected_family": FamilyName.DOCS_SEARCH,
            "selected_tool": "docs_search_v1",
            "query_fingerprint": tracker._query_fingerprint(
                "docs retrieval query"
            ),
            "result_status": AcquisitionStatus.NO_RESULT,
            "result_utility": RetrievalResultUtility.NOT_USEFUL,
            "fallback_applied": True,
        },
    ]
    assert "memory retrieval query" not in str(history_record.retrieval_attempts)


def test_history_tracker_logs_each_skip_reason(caplog) -> None:
    caplog.set_level(logging.INFO)
    tracker = ResearchRetrievalHistoryTracker()

    no_tool_state = _run_state()
    tracker.record_completed_iteration(no_tool_state)
    assert caplog.records[-1].history_skip_reason == "no_tool_execution_result"

    no_need_state = _run_state()
    no_need_state.next_evidence_need = None
    no_need_state.require_current_iteration().tool_execution_result = (
        ToolExecutionLayerResult(
            execution_status="completed",
            acquisition_status=AcquisitionStatus.NO_RESULT,
        )
    )
    tracker.record_completed_iteration(no_need_state)
    assert caplog.records[-1].history_skip_reason == "no_next_evidence_need"

    no_attempt_state = _run_state()
    no_attempt_state.require_current_iteration().tool_execution_result = (
        ToolExecutionLayerResult(
            execution_status="completed",
            acquisition_status=AcquisitionStatus.NO_RESULT,
        )
    )
    tracker.record_completed_iteration(no_attempt_state)
    assert caplog.records[-1].history_skip_reason == "no_retrieval_attempt"

    no_valid_attempt_state = _run_state()
    no_valid_attempt_state.require_current_iteration().tool_execution_result = (
        ToolExecutionLayerResult(
            execution_status="completed",
            acquisition_status=AcquisitionStatus.NO_RESULT,
            retrieval_trace=RetrievalTrace(
                target_problem="补齐当前目标的可靠支撑材料。",
                attempts=[
                    RetrievalAttemptTrace(
                        generated_query="unroutable query",
                        acquisition_status=AcquisitionStatus.NO_RESULT,
                    )
                ],
            ),
        )
    )
    tracker.record_completed_iteration(no_valid_attempt_state)
    assert caplog.records[-1].history_skip_reason == "no_valid_attempt"

    history_records = [
        record
        for record in caplog.records
        if getattr(record, "event", None)
        == "research_retrieval_history_updated"
    ]
    assert [record.history_update_status for record in history_records] == [
        "skipped",
        "skipped",
        "skipped",
        "skipped",
    ]
    assert all(record.new_retrieval_attempt_count == 0 for record in history_records)


def test_memory_low_value_history_switches_current_target_to_external() -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _run_state(
        recent_retrieval_attempts=[
            _attempt(FamilyName.RESEARCH_KNOWLEDGE_RECALL),
        ]
    )
    decider = ResearchActionDecider(retrieval_history_tracker=tracker)
    decider_input = _decider_input(
        ResearchStageInput(
            original_query="补齐当前目标的可靠支撑材料。",
            available_families=[
                FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                FamilyName.DOCS_SEARCH,
            ],
        ),
        state,
    )
    state_before_decision = deepcopy(state)
    input_before_decision = decider_input.model_dump(mode="json")

    output = asyncio.run(decider.decide(decider_input))

    assert output.action_mode == "external_acquisition"
    assert output.action_decision_reason == "memory_blocked_by_history"
    assert output.action_request is not None
    assert output.action_request.allowed_source_families == [
        FamilyName.DOCS_SEARCH
    ]
    assert state == state_before_decision
    assert decider_input.model_dump(mode="json") == input_before_decision


def test_weakly_useful_memory_history_switches_current_target_to_external() -> None:
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

    output = asyncio.run(
        decider.decide(
            _decider_input(
                ResearchStageInput(
                    original_query="补齐当前目标的可靠支撑材料。",
                    available_families=[
                        FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                        FamilyName.DOCS_SEARCH,
                    ],
                ),
                state,
            )
        )
    )

    assert output.action_mode == "external_acquisition"
    assert output.action_decision_reason == "memory_blocked_by_history"
    assert output.action_request is not None
    assert output.action_request.allowed_source_families == [
        FamilyName.DOCS_SEARCH
    ]


def test_weakly_useful_memory_exhausts_memory_only_path() -> None:
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

    output = asyncio.run(
        decider.decide(
            _decider_input(
                ResearchStageInput(
                    original_query="补齐当前目标的可靠支撑材料。",
                    available_families=[
                        FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                    ],
                ),
                state,
            )
        )
    )

    assert output.candidate_action_modes == ["refine_from_existing_state"]
    assert output.action_mode == "refine_from_existing_state"
    assert output.action_decision_reason == "acquisition_paths_exhausted"
    assert output.acquisition_paths_exhausted is True
    assert output.action_request is None


@pytest.mark.parametrize("family", list(FamilyName))
@pytest.mark.parametrize(
    "utility",
    [
        RetrievalResultUtility.WEAKLY_USEFUL,
        RetrievalResultUtility.NOT_USEFUL,
    ],
)
def test_lower_two_utility_levels_make_every_family_low_value(
    family: FamilyName,
    utility: RetrievalResultUtility,
) -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _run_state(
        recent_retrieval_attempts=[
            _attempt(
                family,
                status=AcquisitionStatus.SUCCESS,
                utility=utility,
            )
        ]
    )

    assert tracker.low_value_families_for_target(
        state.recent_retrieval_attempts,
        "objective",
    ) == {family}


@pytest.mark.parametrize("family", list(FamilyName))
@pytest.mark.parametrize(
    "utility",
    [
        RetrievalResultUtility.HIGHLY_USEFUL,
        RetrievalResultUtility.STRONGLY_USEFUL,
        RetrievalResultUtility.USEFUL,
    ],
)
def test_top_three_utility_levels_do_not_block_family(
    family: FamilyName,
    utility: RetrievalResultUtility,
) -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _run_state(
        recent_retrieval_attempts=[
            _attempt(
                family,
                status=AcquisitionStatus.SUCCESS,
                utility=utility,
            )
        ]
    )

    assert tracker.low_value_families_for_target(
        state.recent_retrieval_attempts,
        "objective",
    ) == set()


def test_only_latest_attempt_per_family_controls_low_value_state() -> None:
    tracker = ResearchRetrievalHistoryTracker()
    recovered_attempts = [
        _attempt(
            FamilyName.DOCS_SEARCH,
            status=AcquisitionStatus.SUCCESS,
            utility=RetrievalResultUtility.WEAKLY_USEFUL,
        ),
        _attempt(
            FamilyName.DOCS_SEARCH,
            status=AcquisitionStatus.SUCCESS,
            utility=RetrievalResultUtility.USEFUL,
        ),
    ]
    regressed_attempts = list(reversed(recovered_attempts))

    assert tracker.low_value_families_for_target(
        recovered_attempts,
        "objective",
    ) == set()
    assert tracker.low_value_families_for_target(
        regressed_attempts,
        "objective",
    ) == {FamilyName.DOCS_SEARCH}


@pytest.mark.parametrize(
    ("top_gap_progress", "evidence_gain", "expected_utility"),
    [
        (
            "resolved",
            "meaningful_gain",
            RetrievalResultUtility.HIGHLY_USEFUL,
        ),
        (
            "partially_advanced",
            "meaningful_gain",
            RetrievalResultUtility.STRONGLY_USEFUL,
        ),
        (
            "not_advanced",
            "meaningful_gain",
            RetrievalResultUtility.USEFUL,
        ),
        (
            "partially_advanced",
            "limited_gain",
            RetrievalResultUtility.WEAKLY_USEFUL,
        ),
        (
            "partially_advanced",
            "no_meaningful_gain",
            RetrievalResultUtility.NOT_USEFUL,
        ),
        (
            "not_advanced",
            "failed_acquisition",
            RetrievalResultUtility.NOT_USEFUL,
        ),
    ],
)
def test_attempt_utility_uses_five_level_outcome_mapping(
    top_gap_progress: str,
    evidence_gain: str,
    expected_utility: RetrievalResultUtility,
) -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _state_with_processed_evidence(
        top_gap_progress=top_gap_progress,
        evidence_gain=evidence_gain,
    )

    assert tracker._attempt_utility(state, AcquisitionStatus.SUCCESS) == (
        expected_utility
    )


def test_attempt_utility_without_evaluation_is_weakly_useful() -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _state_with_processed_evidence(
        top_gap_progress=None,
        evidence_gain=None,
    )

    assert tracker._attempt_utility(state, AcquisitionStatus.SUCCESS) == (
        RetrievalResultUtility.WEAKLY_USEFUL
    )


@pytest.mark.parametrize(
    "acquisition_status",
    [AcquisitionStatus.SUCCESS, AcquisitionStatus.PARTIAL_SUCCESS],
)
def test_returned_but_non_advancing_evidence_is_not_useful(
    acquisition_status: AcquisitionStatus,
) -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _state_with_processed_evidence(
        top_gap_progress="not_advanced",
        evidence_gain="no_meaningful_gain",
    )

    assert tracker._attempt_utility(state, acquisition_status) == (
        RetrievalResultUtility.NOT_USEFUL
    )


@pytest.mark.parametrize(
    "acquisition_status",
    [AcquisitionStatus.FAILED, AcquisitionStatus.NO_RESULT],
)
def test_failed_or_empty_acquisition_is_not_useful(
    acquisition_status: AcquisitionStatus,
) -> None:
    tracker = ResearchRetrievalHistoryTracker()

    assert tracker._attempt_utility(_run_state(), acquisition_status) == (
        RetrievalResultUtility.NOT_USEFUL
    )


def test_success_without_processed_evidence_is_not_useful() -> None:
    tracker = ResearchRetrievalHistoryTracker()

    assert tracker._attempt_utility(_run_state(), AcquisitionStatus.SUCCESS) == (
        RetrievalResultUtility.NOT_USEFUL
    )


def test_failed_no_result_and_not_useful_history_remain_low_value() -> None:
    tracker = ResearchRetrievalHistoryTracker()
    attempts = [
        _attempt(
            FamilyName.WEB_SEARCH,
            status=AcquisitionStatus.FAILED,
            utility=RetrievalResultUtility.WEAKLY_USEFUL,
        ),
        _attempt(
            FamilyName.PAPER_SEARCH,
            status=AcquisitionStatus.NO_RESULT,
            utility=RetrievalResultUtility.USEFUL,
        ),
        _attempt(
            FamilyName.DOCS_SEARCH,
            status=AcquisitionStatus.SUCCESS,
            utility=RetrievalResultUtility.NOT_USEFUL,
        ),
    ]

    assert all(tracker.is_definitively_low_value(attempt) for attempt in attempts)


def test_weakly_useful_memory_history_is_scoped_to_coverage_target() -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _run_state(
        recent_retrieval_attempts=[
            _attempt(
                FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                status=AcquisitionStatus.SUCCESS,
                utility=RetrievalResultUtility.WEAKLY_USEFUL,
                target_key="sub_question:1",
            )
        ]
    )

    assert tracker.low_value_families_for_target(
        state.recent_retrieval_attempts,
        "objective",
    ) == set()
    assert tracker.low_value_families_for_target(
        state.recent_retrieval_attempts,
        "sub_question:1",
    ) == {
        FamilyName.RESEARCH_KNOWLEDGE_RECALL
    }


def test_exhausted_memory_and_external_paths_degrade_without_outcome_llm() -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _run_state(
        recent_retrieval_attempts=[
            _attempt(FamilyName.RESEARCH_KNOWLEDGE_RECALL),
            _attempt(FamilyName.DOCS_SEARCH),
        ]
    )
    decider = ResearchActionDecider(retrieval_history_tracker=tracker)

    output = asyncio.run(
        decider.decide(
            _decider_input(
                ResearchStageInput(
                    original_query="补齐当前目标的可靠支撑材料。",
                    available_families=[
                        FamilyName.RESEARCH_KNOWLEDGE_RECALL,
                        FamilyName.DOCS_SEARCH,
                    ],
                ),
                state,
            )
        )
    )
    _apply_decider_output(state, output)
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
    assert output.action_mode == "refine_from_existing_state"
    assert iteration.acquisition_paths_exhausted is True
    assert iteration.action_decision_reason == "acquisition_paths_exhausted"
    assert outcome == "degrade"
    assert iteration.outcome_decision_source == "rule_short_circuit"


def test_iteration_budget_exhaustion_has_explicit_action_reason() -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _run_state()
    state.require_current_iteration().remaining_iteration_budget = 0
    decider = ResearchActionDecider(retrieval_history_tracker=tracker)

    output = asyncio.run(
        decider.decide(
            _decider_input(
                ResearchStageInput(
                    original_query="预算耗尽后停止获取材料。",
                    available_families=[FamilyName.DOCS_SEARCH],
                ),
                state,
            )
        )
    )

    assert output.action_mode == "refine_from_existing_state"
    assert output.action_decision_reason == "iteration_budget_exhausted"
    assert output.action_rationale == (
        "当前 iteration budget 已耗尽，因此不再发起 acquisition。"
    )
