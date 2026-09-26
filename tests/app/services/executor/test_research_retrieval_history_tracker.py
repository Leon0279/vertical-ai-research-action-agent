"""Research Executor 检索历史闭环测试。"""

from __future__ import annotations

import asyncio
import logging

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
    prompt_history = tracker.assessment_prompt_value(state)
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
    assert iteration.action_decision_reason == "memory_blocked_by_history"
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
    iteration = state.require_current_iteration()
    assert iteration.action_mode == "memory_backed_acquisition"
    assert iteration.action_decision_reason == "memory_only_candidate"


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
    assert iteration.action_decision_reason == "acquisition_paths_exhausted"
    assert outcome == "degrade"
    assert iteration.outcome_decision_source == "rule_short_circuit"


def test_iteration_budget_exhaustion_has_explicit_action_reason() -> None:
    tracker = ResearchRetrievalHistoryTracker()
    state = _run_state()
    state.require_current_iteration().remaining_iteration_budget = 0
    decider = ResearchActionDecider(retrieval_history_tracker=tracker)

    should_acquire = asyncio.run(
        decider.decide(
            ResearchStageInput(
                original_query="预算耗尽后停止获取材料。",
                available_families=[FamilyName.DOCS_SEARCH],
            ),
            state,
        )
    )

    iteration = state.require_current_iteration()
    assert should_acquire is False
    assert iteration.action_mode == "refine_from_existing_state"
    assert iteration.action_decision_reason == "iteration_budget_exhausted"
    assert iteration.action_rationale == (
        "当前 iteration budget 已耗尽，因此不再发起 acquisition。"
    )
