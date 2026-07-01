"""Request completion and recovery evaluation service tests."""

from __future__ import annotations

import asyncio

from app.domain.models import (
    BaseFamilyExecutionResult,
    RequestCompletionEvaluationRequest,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)
from app.services.tool_execution_layer.request_completion_evaluation_service import (
    RequestCompletionEvaluationService,
)


def _evaluate(
    request: RequestCompletionEvaluationRequest,
):
    return asyncio.run(RequestCompletionEvaluationService().evaluate(request))


def _outcome(
    *,
    acquisition_status: str,
    selected_family: str = "docs_search",
    selected_tool: str | None = "llms_txt_docs_search_v1",
    candidate_tools: list[str] | None = None,
    normalized_items: list[dict[str, object]] | None = None,
) -> BaseFamilyExecutionResult:
    return BaseFamilyExecutionResult(
        normalized_items=normalized_items or [],
        acquisition_status=acquisition_status,
        dropped_item_count=0,
        source_summary=RetrievalSourceSummary(),
        execution_summary=RetrievalExecutionSummary(),
        retrieval_trace=RetrievalTrace(),
        error_info=None,
        selected_family=selected_family,
        candidate_tools=candidate_tools or ["llms_txt_docs_search_v1"],
        selected_tool=selected_tool,
    )


def _item(item_id: str = "1") -> dict[str, object]:
    return {
        "item_id": item_id,
        "source_family": "docs_search",
        "source_reference": {
            "source_type": "document",
            "source_id": f"doc-{item_id}",
        },
        "content": "Useful content",
    }


def test_success_is_complete_and_stops() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            execution_outcome=_outcome(acquisition_status="success"),
        )
    )

    assert result.evaluation_status == "evaluated"
    assert result.request_completion_status == "complete"
    assert result.request_completed is True
    assert result.needs_recovery is False
    assert result.recovery_action == "stop"
    assert result.next_step_hint == "none"


def test_partial_success_with_continuation_continues() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            continuation_available=True,
            execution_outcome=_outcome(acquisition_status="partial_success"),
        )
    )

    assert result.request_completion_status == "incomplete_recoverable"
    assert result.request_completed is False
    assert result.needs_recovery is True
    assert result.recovery_action == "continue"
    assert result.next_step_hint == "continue_current_request"


def test_partial_success_without_continuation_is_complete() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            execution_outcome=_outcome(acquisition_status="partial_success"),
        )
    )

    assert result.request_completion_status == "complete"
    assert result.request_completed is True
    assert result.needs_recovery is False
    assert result.recovery_action == "stop"


def test_partial_success_at_max_results_stops() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            continuation_available=True,
            max_results=1,
            execution_outcome=_outcome(
                acquisition_status="partial_success",
                normalized_items=[_item()],
            ),
        )
    )

    assert result.request_completion_status == "complete"
    assert result.recovery_action == "stop"


def test_no_result_with_same_family_fallback_uses_same_family_hint() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            fallback_policy="fallback_within_same_family",
            execution_outcome=_outcome(
                acquisition_status="no_result",
                candidate_tools=["tool_a", "tool_b"],
                selected_tool="tool_a",
            ),
        )
    )

    assert result.request_completion_status == "incomplete_recoverable"
    assert result.needs_recovery is True
    assert result.recovery_action == "fallback"
    assert result.next_step_hint == "fallback_within_same_family"


def test_no_result_with_cross_family_fallback_uses_broader_hint() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            fallback_policy="fallback_to_broader_search",
            available_families=["docs_search", "web_search"],
            execution_outcome=_outcome(acquisition_status="no_result"),
        )
    )

    assert result.request_completion_status == "incomplete_recoverable"
    assert result.recovery_action == "fallback"
    assert result.next_step_hint == "fallback_to_broader_search"


def test_no_result_without_fallback_is_unrecoverable() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            fallback_policy="no_fallback",
            execution_outcome=_outcome(acquisition_status="no_result"),
        )
    )

    assert result.request_completion_status == "incomplete_unrecoverable"
    assert result.needs_recovery is False
    assert result.recovery_action == "stop"
    assert result.next_step_hint == "stop_request"


def test_failed_timeout_with_retry_budget_retries_same_tool() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            failure_reason="timeout",
            retry_budget=2,
            retry_count=0,
            execution_outcome=_outcome(acquisition_status="failed"),
        )
    )

    assert result.request_completion_status == "incomplete_recoverable"
    assert result.recovery_action == "retry_same_tool"
    assert result.next_step_hint == "retry_same_tool"


def test_failed_timeout_with_exhausted_retry_and_fallback_falls_back() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            failure_reason="timeout",
            retry_budget=1,
            retry_count=1,
            fallback_policy="fallback_to_broader_search",
            available_families=["docs_search", "web_search"],
            execution_outcome=_outcome(acquisition_status="failed"),
        )
    )

    assert result.recovery_action == "fallback"
    assert result.next_step_hint == "fallback_to_broader_search"


def test_failed_tool_unavailable_prefers_fallback_without_retry() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            failure_reason="tool_unavailable",
            retry_budget=3,
            retry_count=0,
            fallback_policy="fallback_to_broader_search",
            available_families=["docs_search", "web_search"],
            execution_outcome=_outcome(acquisition_status="failed"),
        )
    )

    assert result.recovery_action == "fallback"
    assert result.next_step_hint == "fallback_to_broader_search"


def test_failed_auth_error_stops() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            failure_reason="auth_error",
            execution_outcome=_outcome(acquisition_status="failed"),
        )
    )

    assert result.request_completion_status == "incomplete_unrecoverable"
    assert result.recovery_action == "stop"


def test_failed_invalid_request_stops() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            failure_reason="invalid_request",
            execution_outcome=_outcome(acquisition_status="failed"),
        )
    )

    assert result.request_completion_status == "incomplete_unrecoverable"
    assert result.recovery_action == "stop"


def test_failed_unknown_error_without_retry_or_fallback_stops() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            failure_reason="unknown_error",
            retry_budget=0,
            retry_count=0,
            fallback_policy="no_fallback",
            execution_outcome=_outcome(acquisition_status="failed"),
        )
    )

    assert result.request_completion_status == "incomplete_unrecoverable"
    assert result.recovery_action == "stop"


def test_timeout_budget_exhausted_disables_continue_retry_and_fallback() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            continuation_available=True,
            failure_reason="timeout",
            fallback_policy="fallback_to_broader_search",
            available_families=["docs_search", "web_search"],
            timeout_limit_ms=1000,
            request_elapsed_ms=1000,
            execution_outcome=_outcome(acquisition_status="failed"),
        )
    )

    assert result.request_completion_status == "incomplete_unrecoverable"
    assert result.needs_recovery is False
    assert result.recovery_action == "stop"


def test_selected_family_mismatch_returns_failed() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="web_search",
            execution_outcome=_outcome(
                acquisition_status="success",
                selected_family="docs_search",
            ),
        )
    )

    assert result.evaluation_status == "failed"
    assert result.error_info == "selected_family must match execution_outcome.selected_family."


def test_empty_target_problem_returns_failed() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="  ",
            selected_family="docs_search",
            execution_outcome=_outcome(acquisition_status="success"),
        )
    )

    assert result.evaluation_status == "failed"
    assert result.error_info == "target_problem must not be empty."


def test_evaluation_summary_and_trace_have_expected_shape() -> None:
    result = _evaluate(
        RequestCompletionEvaluationRequest(
            target_problem="Find official API guidance",
            selected_family="docs_search",
            generated_query="Responses API official docs",
            failure_reason="unknown_error",
            retry_budget=1,
            retry_count=1,
            fallback_policy="fallback_to_broader_search",
            fallback_applied=True,
            available_families=["docs_search", "web_search"],
            allowed_source_families=["docs_search", "web_search"],
            blocked_source_families=["paper_search"],
            max_results=5,
            timeout_limit_ms=1000,
            request_elapsed_ms=300,
            execution_outcome=_outcome(acquisition_status="no_result"),
        )
    )

    assert result.evaluation_summary["policy"] == "request_completion_recovery_evaluator_v1"
    assert result.evaluation_summary["selected_family"] == "docs_search"
    assert result.evaluation_trace["generated_query"] == "Responses API official docs"
    assert result.evaluation_trace["candidate_tools"] == ["llms_txt_docs_search_v1"]
    assert result.evaluation_trace["failure_reason"] == "unknown_error"
    assert result.evaluation_trace["fallback_applied"] is True
    assert result.evaluation_trace["same_family_fallback_available"] is False
    assert result.evaluation_trace["cross_family_fallback_available"] is True
