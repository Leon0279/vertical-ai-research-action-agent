"""Research Executor service-private run-state model tests."""

from app.domain.enums import FamilyName
from app.services.executor.models.evidence_coverage_entry import EvidenceCoverageEntry
from app.services.executor.models.research_action_request import ResearchActionRequest
from app.services.executor.models.research_executor_iteration_state import (
    ResearchExecutorIterationState,
)
from app.services.executor.models.research_executor_run_state import (
    ResearchExecutorRunState,
)
from app.services.executor.models.research_iteration_evaluation_state import (
    ResearchIterationEvaluationState,
)


def _coverage_map() -> dict[str, EvidenceCoverageEntry]:
    return {
        "objective": EvidenceCoverageEntry(
            target_type="objective",
            target_text="确认研究目标的证据覆盖情况。",
            coverage_status="not_covered",
            coverage_summary="尚未完成语义覆盖判断。",
        )
    }


def test_research_executor_run_state_uses_typed_defaults() -> None:
    state = ResearchExecutorRunState(evidence_coverage_map=_coverage_map())

    assert state.processed_evidence_units == []
    assert state.identified_gaps == []
    assert state.intermediate_findings == []
    assert state.finding_caveats == []
    assert state.tool_execution_results == []
    assert state.evidence_processing_results == []
    assert state.current_iteration is None
    assert state.evidence_coverage_map["objective"].coverage_status == "not_covered"


def test_research_executor_run_state_requires_current_iteration() -> None:
    state = ResearchExecutorRunState(evidence_coverage_map=_coverage_map())

    try:
        state.require_current_iteration()
    except ValueError as exc:
        assert "current_iteration is required" in str(exc)
    else:
        raise AssertionError("Expected a missing current iteration to raise ValueError.")


def test_iteration_state_keeps_action_and_evaluation_as_typed_models() -> None:
    action_request = ResearchActionRequest(
        action_mode="external_acquisition",
        target_problem="补充当前研究目标的直接事实证据。",
        allowed_source_families=[FamilyName.DOCS_SEARCH],
        preferred_source_families=[FamilyName.DOCS_SEARCH],
        evidence_goal="establish_coverage",
        desired_evidence_kind="direct_fact",
        freshness_requirement="normal",
    )
    iteration = ResearchExecutorIterationState(
        iteration_index=1,
        remaining_iteration_budget=2,
        action_mode="external_acquisition",
        action_request=action_request,
        evaluation_state=ResearchIterationEvaluationState(
            top_gap_progress="partially_advanced",
            evidence_gain="meaningful_gain",
            finding_progress="improved_but_not_stable",
            residual_uncertainty="moderate",
        ),
    )
    state = ResearchExecutorRunState(
        evidence_coverage_map=_coverage_map(),
        current_iteration=iteration,
    )

    assert state.require_current_iteration() is iteration
    assert iteration.action_request is action_request
    assert iteration.action_request.allowed_source_families == [
        FamilyName.DOCS_SEARCH
    ]
    assert iteration.evaluation_state is not None
    assert iteration.evaluation_state.evidence_gain == "meaningful_gain"
