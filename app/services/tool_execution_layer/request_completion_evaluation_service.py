"""Request completion and recovery evaluation service."""

from __future__ import annotations

from typing import Any

from app.domain.enums import AcquisitionStatus, FamilyName
from app.domain.models import (
    RequestCompletionEvaluationRequest,
    RequestCompletionEvaluationResult,
)
from app.services.tool_execution_layer.contracts.request_completion_evaluation_service_protocol import (
    RequestCompletionEvaluationServiceProtocol,
)


class RequestCompletionEvaluationService(RequestCompletionEvaluationServiceProtocol):
    """负责处理请求完成度评估相关业务逻辑的服务。

Evaluate whether one family execution result is complete or needs recovery."""

    _POLICY_NAME = "request_completion_recovery_evaluator_v1"
    _SUPPORTED_FAMILIES = {
        FamilyName.RESEARCH_KNOWLEDGE_RECALL,
        FamilyName.DOCS_SEARCH,
        FamilyName.PAPER_SEARCH,
        FamilyName.WEB_SEARCH,
    }

    async def evaluate(
        self,
        request: RequestCompletionEvaluationRequest,
    ) -> RequestCompletionEvaluationResult:
        """Return a deterministic completion and recovery decision."""

        normalized_request = self._normalize_request(request)
        validation_error = self._validate_request(normalized_request)
        if validation_error is not None:
            return self._failed_result(normalized_request, validation_error)

        timeout_exhausted = self._is_timeout_exhausted(normalized_request)
        reached_max_results = self._has_reached_max_results(normalized_request)
        same_family_fallback_available = self._same_family_fallback_available(
            normalized_request
        )
        cross_family_fallback_available = self._cross_family_fallback_available(
            normalized_request
        )

        acquisition_status = normalized_request.execution_outcome.acquisition_status

        if acquisition_status == AcquisitionStatus.SUCCESS:
            return self._evaluated_result(
                normalized_request,
                request_completion_status="complete",
                request_completed=True,
                needs_recovery=False,
                recovery_action="stop",
                recovery_reason="Execution produced a successful acquisition result.",
                next_step_hint="none",
                same_family_fallback_available=same_family_fallback_available,
                cross_family_fallback_available=cross_family_fallback_available,
            )

        if acquisition_status == AcquisitionStatus.PARTIAL_SUCCESS:
            if (
                normalized_request.continuation_available
                and not reached_max_results
                and not timeout_exhausted
            ):
                return self._evaluated_result(
                    normalized_request,
                    request_completion_status="incomplete_recoverable",
                    request_completed=False,
                    needs_recovery=True,
                    recovery_action="continue",
                    recovery_reason=(
                        "Partial success left continuation available within the current request."
                    ),
                    next_step_hint="continue_current_request",
                    same_family_fallback_available=same_family_fallback_available,
                    cross_family_fallback_available=cross_family_fallback_available,
                )

            return self._evaluated_result(
                normalized_request,
                request_completion_status="complete",
                request_completed=True,
                needs_recovery=False,
                recovery_action="stop",
                recovery_reason=(
                    "Partial success is treated as complete because no continuation path should be used."
                ),
                next_step_hint="none",
                same_family_fallback_available=same_family_fallback_available,
                cross_family_fallback_available=cross_family_fallback_available,
            )

        if acquisition_status == AcquisitionStatus.NO_RESULT:
            if timeout_exhausted:
                return self._evaluated_result(
                    normalized_request,
                    request_completion_status="incomplete_unrecoverable",
                    request_completed=False,
                    needs_recovery=False,
                    recovery_action="stop",
                    recovery_reason="Timeout budget exhausted before any recovery path could be attempted.",
                    next_step_hint="stop_request",
                    same_family_fallback_available=same_family_fallback_available,
                    cross_family_fallback_available=cross_family_fallback_available,
                )
            if same_family_fallback_available:
                return self._evaluated_result(
                    normalized_request,
                    request_completion_status="incomplete_recoverable",
                    request_completed=False,
                    needs_recovery=True,
                    recovery_action="fallback",
                    recovery_reason="No result was returned and another tool remains in the same family.",
                    next_step_hint="fallback_within_same_family",
                    same_family_fallback_available=same_family_fallback_available,
                    cross_family_fallback_available=cross_family_fallback_available,
                )
            if cross_family_fallback_available:
                return self._evaluated_result(
                    normalized_request,
                    request_completion_status="incomplete_recoverable",
                    request_completed=False,
                    needs_recovery=True,
                    recovery_action="fallback",
                    recovery_reason="No result was returned and a broader family fallback path is available.",
                    next_step_hint="fallback_to_broader_search",
                    same_family_fallback_available=same_family_fallback_available,
                    cross_family_fallback_available=cross_family_fallback_available,
                )
            return self._evaluated_result(
                normalized_request,
                request_completion_status="incomplete_unrecoverable",
                request_completed=False,
                needs_recovery=False,
                recovery_action="stop",
                recovery_reason="No result was returned and no recovery path is available.",
                next_step_hint="stop_request",
                same_family_fallback_available=same_family_fallback_available,
                cross_family_fallback_available=cross_family_fallback_available,
            )

        return self._evaluate_failed_outcome(
            normalized_request,
            timeout_exhausted=timeout_exhausted,
            same_family_fallback_available=same_family_fallback_available,
            cross_family_fallback_available=cross_family_fallback_available,
        )

    def _normalize_request(
        self,
        request: RequestCompletionEvaluationRequest,
    ) -> RequestCompletionEvaluationRequest:
        return RequestCompletionEvaluationRequest(
            target_problem=request.target_problem.strip(),
            selected_family=request.selected_family,
            generated_query=(request.generated_query or "").strip() or None,
            execution_outcome=request.execution_outcome,
            failure_reason=request.failure_reason,
            continuation_available=request.continuation_available,
            retry_budget=request.retry_budget,
            retry_count=request.retry_count,
            fallback_policy=request.fallback_policy,
            fallback_applied=request.fallback_applied,
            max_results=request.max_results,
            timeout_limit_ms=request.timeout_limit_ms,
            request_elapsed_ms=request.request_elapsed_ms,
            available_families=self._normalize_family_list(request.available_families),
            allowed_source_families=self._normalize_family_list(
                request.allowed_source_families
            ),
            blocked_source_families=self._normalize_family_list(
                request.blocked_source_families
            ),
        )

    def _normalize_family_list(self, families: list[FamilyName]) -> list[FamilyName]:
        normalized: list[FamilyName] = []
        seen: set[FamilyName] = set()
        for family in families:
            normalized_family = FamilyName(str(family).strip())
            if normalized_family in seen:
                continue
            normalized.append(normalized_family)
            seen.add(normalized_family)
        return normalized

    def _validate_request(
        self,
        request: RequestCompletionEvaluationRequest,
    ) -> str | None:
        if not request.target_problem:
            return "target_problem must not be empty."
        if request.retry_budget < 0:
            return "retry_budget must be greater than or equal to 0."
        if request.retry_count < 0:
            return "retry_count must be greater than or equal to 0."
        if request.max_results is not None and request.max_results < 1:
            return "max_results must be greater than or equal to 1."
        if request.timeout_limit_ms is not None and request.timeout_limit_ms <= 0:
            return "timeout_limit_ms must be greater than 0."
        if request.request_elapsed_ms is not None and request.request_elapsed_ms < 0:
            return "request_elapsed_ms must be greater than or equal to 0."
        if request.selected_family != request.execution_outcome.selected_family:
            return (
                "selected_family must match execution_outcome.selected_family."
            )
        return None

    def _same_family_fallback_available(
        self,
        request: RequestCompletionEvaluationRequest,
    ) -> bool:
        return (
            request.fallback_policy != "no_fallback"
            and request.fallback_policy == "fallback_within_same_family"
            and len(request.execution_outcome.candidate_tools) > 1
            and request.execution_outcome.selected_tool is not None
        )

    def _cross_family_fallback_available(
        self,
        request: RequestCompletionEvaluationRequest,
    ) -> bool:
        if request.fallback_policy != "fallback_to_broader_search":
            return False

        candidate_families = (
            request.available_families
            if request.available_families
            else sorted(self._SUPPORTED_FAMILIES)
        )
        filtered = [
            family
            for family in candidate_families
            if family in self._SUPPORTED_FAMILIES
        ]
        if request.allowed_source_families:
            allowed = set(request.allowed_source_families)
            filtered = [family for family in filtered if family in allowed]
        blocked = set(request.blocked_source_families)
        filtered = [
            family
            for family in filtered
            if family not in blocked and family != request.selected_family
        ]
        return bool(filtered)

    def _has_reached_max_results(
        self,
        request: RequestCompletionEvaluationRequest,
    ) -> bool:
        return request.max_results is not None and (
            len(request.execution_outcome.normalized_items) >= request.max_results
        )

    def _is_timeout_exhausted(
        self,
        request: RequestCompletionEvaluationRequest,
    ) -> bool:
        return (
            request.timeout_limit_ms is not None
            and request.request_elapsed_ms is not None
            and request.request_elapsed_ms >= request.timeout_limit_ms
        )

    def _evaluate_failed_outcome(
        self,
        request: RequestCompletionEvaluationRequest,
        *,
        timeout_exhausted: bool,
        same_family_fallback_available: bool,
        cross_family_fallback_available: bool,
    ) -> RequestCompletionEvaluationResult:
        if timeout_exhausted:
            return self._evaluated_result(
                request,
                request_completion_status="incomplete_unrecoverable",
                request_completed=False,
                needs_recovery=False,
                recovery_action="stop",
                recovery_reason="Timeout budget exhausted before recovery could proceed.",
                next_step_hint="stop_request",
                same_family_fallback_available=same_family_fallback_available,
                cross_family_fallback_available=cross_family_fallback_available,
            )

        retry_available = request.retry_count < request.retry_budget
        fallback_available = (
            same_family_fallback_available or cross_family_fallback_available
        )
        failure_reason = request.failure_reason or "unknown_error"

        if failure_reason in {"timeout", "rate_limited"}:
            if retry_available:
                return self._retry_result(
                    request,
                    reason="Execution failed but retry budget remains for a transient failure.",
                    same_family_fallback_available=same_family_fallback_available,
                    cross_family_fallback_available=cross_family_fallback_available,
                )
            if fallback_available:
                return self._fallback_result(
                    request,
                    reason="Transient execution failure exhausted retries, so fallback should be used.",
                    same_family_fallback_available=same_family_fallback_available,
                    cross_family_fallback_available=cross_family_fallback_available,
                )
            return self._stop_unrecoverable_result(
                request,
                reason="Transient execution failure has no retry budget and no fallback path.",
                same_family_fallback_available=same_family_fallback_available,
                cross_family_fallback_available=cross_family_fallback_available,
            )

        if failure_reason == "tool_error":
            if fallback_available:
                return self._fallback_result(
                    request,
                    reason="Tool error prefers a fallback path over repeating the same tool.",
                    same_family_fallback_available=same_family_fallback_available,
                    cross_family_fallback_available=cross_family_fallback_available,
                )
            if retry_available:
                return self._retry_result(
                    request,
                    reason="Tool error has no fallback path, so one conservative retry is allowed.",
                    same_family_fallback_available=same_family_fallback_available,
                    cross_family_fallback_available=cross_family_fallback_available,
                )
            return self._stop_unrecoverable_result(
                request,
                reason="Tool error has neither fallback nor retry budget available.",
                same_family_fallback_available=same_family_fallback_available,
                cross_family_fallback_available=cross_family_fallback_available,
            )

        if failure_reason in {"malformed_response", "tool_unavailable"}:
            if fallback_available:
                return self._fallback_result(
                    request,
                    reason=(
                        "Execution failure should move to fallback because retrying the same tool is not preferred."
                    ),
                    same_family_fallback_available=same_family_fallback_available,
                    cross_family_fallback_available=cross_family_fallback_available,
                )
            return self._stop_unrecoverable_result(
                request,
                reason="Execution failure has no fallback path available.",
                same_family_fallback_available=same_family_fallback_available,
                cross_family_fallback_available=cross_family_fallback_available,
            )

        if failure_reason in {"auth_error", "invalid_request"}:
            return self._stop_unrecoverable_result(
                request,
                reason="Execution failed with a non-recoverable request or authorization error.",
                same_family_fallback_available=same_family_fallback_available,
                cross_family_fallback_available=cross_family_fallback_available,
            )

        if retry_available:
            return self._retry_result(
                request,
                reason="Unknown execution failure still has retry budget available.",
                same_family_fallback_available=same_family_fallback_available,
                cross_family_fallback_available=cross_family_fallback_available,
            )
        if fallback_available:
            return self._fallback_result(
                request,
                reason="Unknown execution failure exhausted retries, so fallback should be used.",
                same_family_fallback_available=same_family_fallback_available,
                cross_family_fallback_available=cross_family_fallback_available,
            )
        return self._stop_unrecoverable_result(
            request,
            reason="Unknown execution failure has no retry budget and no fallback path.",
            same_family_fallback_available=same_family_fallback_available,
            cross_family_fallback_available=cross_family_fallback_available,
        )

    def _retry_result(
        self,
        request: RequestCompletionEvaluationRequest,
        *,
        reason: str,
        same_family_fallback_available: bool,
        cross_family_fallback_available: bool,
    ) -> RequestCompletionEvaluationResult:
        return self._evaluated_result(
            request,
            request_completion_status="incomplete_recoverable",
            request_completed=False,
            needs_recovery=True,
            recovery_action="retry_same_tool",
            recovery_reason=reason,
            next_step_hint="retry_same_tool",
            same_family_fallback_available=same_family_fallback_available,
            cross_family_fallback_available=cross_family_fallback_available,
        )

    def _fallback_result(
        self,
        request: RequestCompletionEvaluationRequest,
        *,
        reason: str,
        same_family_fallback_available: bool,
        cross_family_fallback_available: bool,
    ) -> RequestCompletionEvaluationResult:
        next_step_hint = (
            "fallback_within_same_family"
            if same_family_fallback_available
            else "fallback_to_broader_search"
        )
        return self._evaluated_result(
            request,
            request_completion_status="incomplete_recoverable",
            request_completed=False,
            needs_recovery=True,
            recovery_action="fallback",
            recovery_reason=reason,
            next_step_hint=next_step_hint,
            same_family_fallback_available=same_family_fallback_available,
            cross_family_fallback_available=cross_family_fallback_available,
        )

    def _stop_unrecoverable_result(
        self,
        request: RequestCompletionEvaluationRequest,
        *,
        reason: str,
        same_family_fallback_available: bool,
        cross_family_fallback_available: bool,
    ) -> RequestCompletionEvaluationResult:
        return self._evaluated_result(
            request,
            request_completion_status="incomplete_unrecoverable",
            request_completed=False,
            needs_recovery=False,
            recovery_action="stop",
            recovery_reason=reason,
            next_step_hint="stop_request",
            same_family_fallback_available=same_family_fallback_available,
            cross_family_fallback_available=cross_family_fallback_available,
        )

    def _failed_result(
        self,
        request: RequestCompletionEvaluationRequest,
        error_info: str,
    ) -> RequestCompletionEvaluationResult:
        return RequestCompletionEvaluationResult(
            evaluation_status="failed",
            request_completion_status=None,
            request_completed=False,
            needs_recovery=False,
            recovery_action=None,
            recovery_reason=None,
            next_step_hint=None,
            evaluation_summary=self._evaluation_summary(
                request=request,
                request_completion_status=None,
                recovery_action=None,
            ),
            evaluation_trace=self._evaluation_trace(
                request=request,
                same_family_fallback_available=False,
                cross_family_fallback_available=False,
            ),
            error_info=error_info,
        )

    def _evaluated_result(
        self,
        request: RequestCompletionEvaluationRequest,
        *,
        request_completion_status: str,
        request_completed: bool,
        needs_recovery: bool,
        recovery_action: str,
        recovery_reason: str,
        next_step_hint: str,
        same_family_fallback_available: bool,
        cross_family_fallback_available: bool,
    ) -> RequestCompletionEvaluationResult:
        return RequestCompletionEvaluationResult(
            evaluation_status="evaluated",
            request_completion_status=request_completion_status,
            request_completed=request_completed,
            needs_recovery=needs_recovery,
            recovery_action=recovery_action,
            recovery_reason=recovery_reason,
            next_step_hint=next_step_hint,
            evaluation_summary=self._evaluation_summary(
                request=request,
                request_completion_status=request_completion_status,
                recovery_action=recovery_action,
            ),
            evaluation_trace=self._evaluation_trace(
                request=request,
                same_family_fallback_available=same_family_fallback_available,
                cross_family_fallback_available=cross_family_fallback_available,
            ),
            error_info=None,
        )

    def _evaluation_summary(
        self,
        *,
        request: RequestCompletionEvaluationRequest,
        request_completion_status: str | None,
        recovery_action: str | None,
    ) -> dict[str, Any]:
        return {
            "selected_family": request.selected_family,
            "selected_tool": request.execution_outcome.selected_tool,
            "acquisition_status": request.execution_outcome.acquisition_status,
            "request_completion_status": request_completion_status,
            "recovery_action": recovery_action,
            "policy": self._POLICY_NAME,
        }

    def _evaluation_trace(
        self,
        *,
        request: RequestCompletionEvaluationRequest,
        same_family_fallback_available: bool,
        cross_family_fallback_available: bool,
    ) -> dict[str, Any]:
        return {
            "target_problem": request.target_problem,
            "generated_query": request.generated_query,
            "selected_family": request.selected_family,
            "selected_tool": request.execution_outcome.selected_tool,
            "candidate_tools": request.execution_outcome.candidate_tools,
            "acquisition_status": request.execution_outcome.acquisition_status,
            "failure_reason": request.failure_reason,
            "continuation_available": request.continuation_available,
            "retry_budget": request.retry_budget,
            "retry_count": request.retry_count,
            "fallback_policy": request.fallback_policy,
            "fallback_applied": request.fallback_applied,
            "available_families": request.available_families,
            "allowed_source_families": request.allowed_source_families,
            "blocked_source_families": request.blocked_source_families,
            "same_family_fallback_available": same_family_fallback_available,
            "cross_family_fallback_available": cross_family_fallback_available,
            "max_results": request.max_results,
            "timeout_limit_ms": request.timeout_limit_ms,
            "request_elapsed_ms": request.request_elapsed_ms,
        }
