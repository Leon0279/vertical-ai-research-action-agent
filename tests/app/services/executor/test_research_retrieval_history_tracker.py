"""Research Executor 检索历史闭环测试。"""

from __future__ import annotations

import logging

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
    RetrievalAttemptTrace,
    RetrievalTrace,
    ToolExecutionLayerResult,
)
from app.services.executor.models.evidence_coverage_entry import EvidenceCoverageEntry
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
from app.services.executor.research_retrieval_history_tracker import (
    ResearchRetrievalHistoryTracker,
)




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
        for index in range(30)
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

    assert len(state.recent_retrieval_attempts) == 30
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
    assert prompt_history[-2]["generated_query"] == "memory retrieval query"
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
    assert history_record.retrieval_history_count == 30
    assert history_record.retrieval_history_truncated_count == 2
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
            "query_fingerprint": tracker.query_fingerprint(
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
