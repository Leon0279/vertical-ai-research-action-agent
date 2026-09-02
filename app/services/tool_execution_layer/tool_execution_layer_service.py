"""Tool Execution Layer coordination service."""

from __future__ import annotations

import logging
from typing import Any, Literal

from app.common.observability import (
    retrieval_query_log_fields,
    sanitize_sensitive_text,
)
from app.common.utils.text import unique_non_empty_strings
from app.domain.enums import AcquisitionStatus, FamilyName, RetrievalResultUtility
from app.domain.models import (
    BaseFamilyExecutionResult,
    DocsSearchFamilyRequest,
    FamilySelectionRequest,
    FamilySelectionResult,
    PaperSearchFamilyRequest,
    RequestCompletionEvaluationRequest,
    RequestCompletionEvaluationResult,
    ResearchKnowledgeRecallFamilyRequest,
    RetrievalQueryGenerationRequest,
    RetrievalQueryGenerationResult,
    ToolExecutionLayerRequest,
    ToolExecutionLayerResult,
    WebSearchFamilyRequest,
)
from app.domain.models.retrieval import (
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)
from app.services.families.contracts.docs_search_family_service_protocol import (
    DocsSearchFamilyServiceProtocol,
)
from app.services.families.contracts.paper_search_family_service_protocol import (
    PaperSearchFamilyServiceProtocol,
)
from app.services.families.contracts.research_knowledge_recall_family_service_protocol import (
    ResearchKnowledgeRecallFamilyServiceProtocol,
)
from app.services.families.contracts.web_search_family_service_protocol import (
    WebSearchFamilyServiceProtocol,
)
from app.services.tool_execution_layer._normalization import normalize_family_list
from app.services.tool_execution_layer.contracts.family_selection_service_protocol import (
    FamilySelectionServiceProtocol,
)
from app.services.tool_execution_layer.contracts.request_completion_evaluation_service_protocol import (
    RequestCompletionEvaluationServiceProtocol,
)
from app.services.tool_execution_layer.contracts.retrieval_query_generation_service_protocol import (
    RetrievalQueryGenerationServiceProtocol,
)
from app.services.tool_execution_layer.contracts.tool_execution_layer_service_protocol import (
    ToolExecutionLayerServiceProtocol,
)
from app.services.tool_execution_layer.models.tool_execution_layer_attempt_outcome import (
    ToolExecutionLayerAttemptOutcome,
)
from app.services.tool_execution_layer.models.tool_execution_layer_run_state import (
    ToolExecutionLayerRunState,
)

_ExecutionDirective = Literal["continue", "complete"]
logger = logging.getLogger(__name__)


class ToolExecutionLayerService(ToolExecutionLayerServiceProtocol):
    """负责处理工具执行层相关业务逻辑的服务。

Coordinate one bounded Tool Execution Layer request for Research Executor."""

    _POLICY_NAME = "tool_execution_layer_single_request_v1"

    def __init__(
        self,
        *,
        family_selection_service: FamilySelectionServiceProtocol,
        query_generation_service: RetrievalQueryGenerationServiceProtocol,
        completion_evaluation_service: RequestCompletionEvaluationServiceProtocol,
        docs_search_family_service: DocsSearchFamilyServiceProtocol | None = None,
        paper_search_family_service: PaperSearchFamilyServiceProtocol | None = None,
        web_search_family_service: WebSearchFamilyServiceProtocol | None = None,
        research_knowledge_recall_family_service: (
            ResearchKnowledgeRecallFamilyServiceProtocol | None
        ) = None,
    ) -> None:
        self._family_selection_service = family_selection_service
        self._query_generation_service = query_generation_service
        self._completion_evaluation_service = completion_evaluation_service
        self._family_services = {
            FamilyName.DOCS_SEARCH: docs_search_family_service,
            FamilyName.PAPER_SEARCH: paper_search_family_service,
            FamilyName.WEB_SEARCH: web_search_family_service,
            FamilyName.RESEARCH_KNOWLEDGE_RECALL: research_knowledge_recall_family_service,
        }

    async def execute(
        self,
        request: ToolExecutionLayerRequest,
    ) -> ToolExecutionLayerResult:
        """Execute family selection, query generation, family execution, and evaluation."""

        normalized_request = self._normalize_request(request)
        injected_families = self._injected_families()
        effective_available_families = self._effective_available_families(
            normalized_request,
            injected_families,
        )
        state = self._create_execution_state(normalized_request)

        while True:
            attempt_outcome = await self._run_attempt(
                request=normalized_request,
                state=state,
                available_families=effective_available_families,
            )
            if attempt_outcome.error_info is not None:
                result = self._failed_from_state(
                    request=normalized_request,
                    state=state,
                    error_info=attempt_outcome.error_info,
                )
                self._log_request_result(result)
                return result

            self._record_attempt(state, attempt_outcome)
            directive = self._apply_evaluation_result(
                request=normalized_request,
                state=state,
                attempt_outcome=attempt_outcome,
            )
            if directive == "continue":
                continue
            result = self._completed_from_state(
                request=normalized_request,
                state=state,
            )
            self._log_request_result(result)
            return result

    def _create_execution_state(
        self,
        request: ToolExecutionLayerRequest,
    ) -> ToolExecutionLayerRunState:
        return ToolExecutionLayerRunState(
            blocked_families=list(request.blocked_source_families),
        )

    async def _run_attempt(
        self,
        *,
        request: ToolExecutionLayerRequest,
        state: ToolExecutionLayerRunState,
        available_families: list[FamilyName],
    ) -> ToolExecutionLayerAttemptOutcome:
        attempt_outcome = await self._prepare_attempt_family_and_query(
            request=request,
            state=state,
            available_families=available_families,
        )
        if attempt_outcome.error_info is not None:
            return attempt_outcome

        validation_error = self._validate_attempt_ready(
            request=request,
            attempt_outcome=attempt_outcome,
        )
        if validation_error is not None:
            attempt_outcome.error_info = validation_error
            return attempt_outcome

        return await self._run_family_and_evaluate(
            request=request,
            state=state,
            attempt_outcome=attempt_outcome,
            available_families=available_families,
        )

    async def _prepare_attempt_family_and_query(
        self,
        *,
        request: ToolExecutionLayerRequest,
        state: ToolExecutionLayerRunState,
        available_families: list[FamilyName],
    ) -> ToolExecutionLayerAttemptOutcome:
        if state.retry_context is not None:
            selected_family, query_generation_result = state.retry_context
            state.retry_context = None
            return ToolExecutionLayerAttemptOutcome(
                selected_family=selected_family,
                query_generation_result=query_generation_result,
            )

        selection_result = await self._select_family(
            request=request,
            available_families=available_families,
            blocked_families=state.blocked_families,
        )
        state.latest_selection = selection_result
        if (
            selection_result.selection_status != "selected"
            or not selection_result.selected_family
        ):
            return ToolExecutionLayerAttemptOutcome(
                error_info=selection_result.error_info
                or "No family was selected for Tool Execution Layer request.",
            )

        selected_family = selection_result.selected_family
        query_generation_result = await self._generate_query(
            request=request,
            selected_family=selected_family,
        )
        state.latest_query_generation = query_generation_result
        return ToolExecutionLayerAttemptOutcome(
            selected_family=selected_family,
            query_generation_result=query_generation_result,
        )

    def _validate_attempt_ready(
        self,
        *,
        request: ToolExecutionLayerRequest,
        attempt_outcome: ToolExecutionLayerAttemptOutcome,
    ) -> str | None:
        selected_family = attempt_outcome.selected_family
        query_generation_result = attempt_outcome.query_generation_result
        if selected_family is None:
            return "No selected family is available for Tool Execution Layer attempt."
        if query_generation_result is None:
            return "Retry requested without a generated query."

        family_service = self._family_services.get(selected_family)
        if family_service is None:
            return f"No family service registered for selected family '{selected_family}'."

        if (
            query_generation_result.generation_status != "succeeded"
            or not query_generation_result.generated_query
        ):
            return (
                query_generation_result.error_info
                or "Query generation did not produce a usable query."
            )

        if selected_family == FamilyName.RESEARCH_KNOWLEDGE_RECALL and not request.owner_user_id:
            return "owner_user_id is required for research_knowledge_recall family."
        return None

    async def _run_family_and_evaluate(
        self,
        *,
        request: ToolExecutionLayerRequest,
        state: ToolExecutionLayerRunState,
        attempt_outcome: ToolExecutionLayerAttemptOutcome,
        available_families: list[FamilyName],
    ) -> ToolExecutionLayerAttemptOutcome:
        selected_family = attempt_outcome.selected_family
        query_generation_result = attempt_outcome.query_generation_result
        if selected_family is None or query_generation_result is None:
            attempt_outcome.error_info = (
                "Attempt cannot run without selected family and generated query."
            )
            return attempt_outcome

        family_service = self._family_services[selected_family]
        generated_query = query_generation_result.generated_query or ""
        family_result, execution_failure_reason = await self._execute_family(
            request=request,
            selected_family=selected_family,
            generated_query=generated_query,
            family_service=family_service,
        )
        state.latest_family_result = family_result
        attempt_outcome.family_result = family_result
        attempt_outcome.execution_failure_reason = execution_failure_reason

        evaluation_result = await self._evaluate_completion(
            request=request,
            selected_family=selected_family,
            generated_query=generated_query,
            family_result=family_result,
            failure_reason=execution_failure_reason,
            retry_count=state.retry_count,
            fallback_applied=state.fallback_applied,
            available_families=available_families,
            blocked_families=state.blocked_families,
        )
        state.latest_evaluation = evaluation_result
        attempt_outcome.evaluation_result = evaluation_result
        if evaluation_result.evaluation_status == "failed":
            attempt_outcome.error_info = (
                evaluation_result.error_info
                or "Request completion evaluation failed."
            )
        return attempt_outcome

    def _record_attempt(
        self,
        state: ToolExecutionLayerRunState,
        attempt_outcome: ToolExecutionLayerAttemptOutcome,
    ) -> None:
        if (
            attempt_outcome.selected_family is None
            or attempt_outcome.query_generation_result is None
            or attempt_outcome.family_result is None
            or attempt_outcome.evaluation_result is None
        ):
            return
        attempt = self._attempt_trace(
            selected_family=attempt_outcome.selected_family,
            selected_tool=attempt_outcome.family_result.selected_tool,
            query_generation_result=attempt_outcome.query_generation_result,
            family_result=attempt_outcome.family_result,
            evaluation_result=attempt_outcome.evaluation_result,
            execution_failure_reason=attempt_outcome.execution_failure_reason,
            retry_count=state.retry_count,
            fallback_applied=state.fallback_applied,
        )
        state.attempts.append(attempt)
        failed = attempt_outcome.family_result.acquisition_status == AcquisitionStatus.FAILED
        logger.log(
            logging.WARNING if failed else logging.INFO,
            "Retrieval attempt completed.",
            extra={
                "event": "retrieval_attempt_completed",
                "attempt_index": len(state.attempts),
                "selected_family": attempt["selected_family"],
                "selected_tool": attempt["selected_tool"],
                **retrieval_query_log_fields(attempt["generated_query"]),
                "acquisition_status": attempt["acquisition_status"],
                "evaluation_status": attempt["evaluation_status"],
                "recovery_action": attempt["recovery_action"],
                "next_step_hint": attempt["next_step_hint"],
                "retry_count": attempt["retry_count"],
                "fallback_applied": attempt["fallback_applied"],
                "failure_stage": attempt.get("failure_stage"),
                "failure_reason": attempt.get("failure_reason"),
                "error_category": attempt.get("error_category"),
                "attempt_error_info": attempt.get("attempt_error_info"),
                "provider_http_status": attempt.get("provider_http_status"),
                "retryable": attempt.get("retryable"),
                "exception_type": attempt.get("exception_type"),
            },
        )

    def _log_request_result(self, result: ToolExecutionLayerResult) -> None:
        """Write one bounded TEL request summary without material or prompt data."""

        summary = result.execution_summary
        trace = result.retrieval_trace
        failed = result.execution_status == "failed"
        logger.log(
            logging.WARNING if failed else logging.INFO,
            "Retrieval request failed." if failed else "Retrieval request completed.",
            extra={
                "event": (
                    "retrieval_request_failed"
                    if failed
                    else "retrieval_request_completed"
                ),
                "execution_status": result.execution_status,
                "acquisition_status": result.acquisition_status,
                "attempt_count": len(trace.attempts),
                "retry_count": summary.retry_count,
                "fallback_applied": summary.fallback_applied,
                "recovery_attempt_count": summary.recovery_attempt_count,
                "recovery_exhausted_reason": summary.recovery_exhausted_reason,
                "error_info": result.error_info,
            },
        )

    def _apply_evaluation_result(
        self,
        *,
        request: ToolExecutionLayerRequest,
        state: ToolExecutionLayerRunState,
        attempt_outcome: ToolExecutionLayerAttemptOutcome,
    ) -> _ExecutionDirective:
        evaluation_result = attempt_outcome.evaluation_result
        selected_family = attempt_outcome.selected_family
        query_generation_result = attempt_outcome.query_generation_result
        if (
            evaluation_result is None
            or selected_family is None
            or query_generation_result is None
        ):
            state.recovery_exhausted_reason = "recovery_action_not_executable"
            return "complete"

        if evaluation_result.recovery_action == "stop":
            return "complete"

        if evaluation_result.recovery_action == "retry_same_tool":
            if state.retry_count >= request.retry_budget:
                state.recovery_exhausted_reason = "retry_budget_exhausted"
                return "complete"
            state.retry_count += 1
            state.recovery_attempt_count += 1
            state.retry_context = (selected_family, query_generation_result)
            return "continue"

        if (
            evaluation_result.recovery_action == "fallback"
            and evaluation_result.next_step_hint == "fallback_to_broader_search"
        ):
            if selected_family not in state.blocked_families:
                state.blocked_families.append(selected_family)
            if state.fallback_applied:
                state.recovery_exhausted_reason = "fallback_already_applied"
                return "complete"
            state.fallback_applied = True
            state.recovery_attempt_count += 1
            return "continue"

        state.recovery_exhausted_reason = (
            "same_family_fallback_not_executable"
            if evaluation_result.next_step_hint == "fallback_within_same_family"
            else "continuation_not_supported"
            if evaluation_result.next_step_hint == "continue_current_request"
            else "recovery_action_not_executable"
        )
        return "complete"

    def _completed_from_state(
        self,
        *,
        request: ToolExecutionLayerRequest,
        state: ToolExecutionLayerRunState,
    ) -> ToolExecutionLayerResult:
        if state.latest_family_result is None:
            return self._failed_from_state(
                request=request,
                state=state,
                error_info="No family execution result available.",
            )
        return self._completed_result(
            request=request,
            family_selection_result=state.latest_selection,
            query_generation_result=state.latest_query_generation,
            family_execution_result=state.latest_family_result,
            completion_evaluation_result=state.latest_evaluation,
            retry_count=state.retry_count,
            fallback_applied=state.fallback_applied,
            recovery_attempt_count=state.recovery_attempt_count,
            attempts=state.attempts,
            recovery_exhausted_reason=state.recovery_exhausted_reason,
        )

    def _failed_from_state(
        self,
        *,
        request: ToolExecutionLayerRequest,
        state: ToolExecutionLayerRunState,
        error_info: str,
    ) -> ToolExecutionLayerResult:
        return self._failed_result(
            request=request,
            family_selection_result=state.latest_selection,
            query_generation_result=state.latest_query_generation,
            family_execution_result=state.latest_family_result,
            completion_evaluation_result=state.latest_evaluation,
            retry_count=state.retry_count,
            fallback_applied=state.fallback_applied,
            recovery_attempt_count=state.recovery_attempt_count,
            attempts=state.attempts,
            error_info=error_info,
            recovery_exhausted_reason=state.recovery_exhausted_reason,
        )

    def _normalize_request(
        self,
        request: ToolExecutionLayerRequest,
    ) -> ToolExecutionLayerRequest:
        return ToolExecutionLayerRequest(
            target_problem=request.target_problem.strip(),
            action_mode=request.action_mode,
            evidence_goal=(request.evidence_goal or "").strip() or None,
            evidence_shape=request.evidence_shape,
            task_framing=(request.task_framing or "").strip() or None,
            allowed_source_families=normalize_family_list(
                request.allowed_source_families
            ),
            preferred_source_families=normalize_family_list(
                request.preferred_source_families
            ),
            blocked_source_families=normalize_family_list(
                request.blocked_source_families
            ),
            available_families=normalize_family_list(request.available_families),
            success_hint=(request.success_hint or "").strip() or None,
            recent_low_value_queries=unique_non_empty_strings(
                request.recent_low_value_queries
            ),
            recent_retrieval_attempts=list(request.recent_retrieval_attempts),
            preferred_tool=(request.preferred_tool or "").strip() or None,
            source_names=unique_non_empty_strings(request.source_names),
            include_domains=unique_non_empty_strings(request.include_domains),
            exclude_domains=unique_non_empty_strings(request.exclude_domains),
            max_search_results=request.max_search_results,
            max_content_fetches=request.max_content_fetches,
            min_score_threshold=request.min_score_threshold,
            owner_user_id=(request.owner_user_id or "").strip() or None,
            query_embedding=request.query_embedding,
            project_scope_id=(request.project_scope_id or "").strip() or None,
            allowed_visibility_scopes=unique_non_empty_strings(
                request.allowed_visibility_scopes
            ),
            knowledge_types=unique_non_empty_strings(request.knowledge_types),
            topic_tags=unique_non_empty_strings(request.topic_tags),
            source_types=unique_non_empty_strings(request.source_types),
            memory_recall_limit=request.memory_recall_limit,
            retry_budget=request.retry_budget,
            fallback_policy=request.fallback_policy,
            timeout_limit_ms=request.timeout_limit_ms,
        )

    def _injected_families(self) -> list[FamilyName]:
        return [
            family
            for family, service in self._family_services.items()
            if service is not None
        ]

    def _effective_available_families(
        self,
        request: ToolExecutionLayerRequest,
        injected_families: list[FamilyName],
    ) -> list[FamilyName]:
        if not request.available_families:
            return injected_families
        injected = set(injected_families)
        return [family for family in request.available_families if family in injected]

    async def _select_family(
        self,
        *,
        request: ToolExecutionLayerRequest,
        available_families: list[FamilyName],
        blocked_families: list[FamilyName],
    ) -> FamilySelectionResult:
        merged_blocked = normalize_family_list(
            [*request.blocked_source_families, *blocked_families]
        )
        return await self._family_selection_service.select_family(
            FamilySelectionRequest(
                target_problem=request.target_problem,
                action_mode=request.action_mode,
                evidence_goal=request.evidence_goal,
                evidence_shape=request.evidence_shape,
                task_framing=request.task_framing,
                allowed_source_families=request.allowed_source_families,
                preferred_source_families=request.preferred_source_families,
                blocked_source_families=merged_blocked,
                available_families=available_families,
            )
        )

    async def _generate_query(
        self,
        *,
        request: ToolExecutionLayerRequest,
        selected_family: FamilyName,
    ) -> RetrievalQueryGenerationResult:
        return await self._query_generation_service.generate_query(
            RetrievalQueryGenerationRequest(
                selected_family=selected_family,
                target_problem=request.target_problem,
                evidence_goal=request.evidence_goal,
                evidence_shape=request.evidence_shape,
                success_hint=request.success_hint,
                task_framing=request.task_framing,
                recent_low_value_queries=(
                    self._recent_low_value_queries_for_selected_family(
                        request,
                        selected_family,
                    )
                ),
            )
        )

    def _recent_low_value_queries_for_selected_family(
        self,
        request: ToolExecutionLayerRequest,
        selected_family: FamilyName,
    ) -> list[str]:
        """合并显式负例与同问题、同 family 的已验证低价值历史 query。"""

        history_queries = [
            attempt.generated_query
            for attempt in request.recent_retrieval_attempts
            if (
                attempt.selected_family == selected_family
                and attempt.target_problem == request.target_problem
                and attempt.generated_query is not None
                and (
                    attempt.result_status
                    in {AcquisitionStatus.FAILED, AcquisitionStatus.NO_RESULT}
                    or (
                        attempt.result_status != AcquisitionStatus.PARTIAL_SUCCESS
                        and attempt.result_utility
                        == RetrievalResultUtility.NOT_USEFUL
                    )
                )
            )
        ]
        return unique_non_empty_strings(
            [*request.recent_low_value_queries, *history_queries]
        )[:3]

    async def _execute_family(
        self,
        *,
        request: ToolExecutionLayerRequest,
        selected_family: FamilyName,
        generated_query: str,
        family_service: Any,
    ) -> tuple[BaseFamilyExecutionResult, str | None]:
        try:
            family_request = self._build_family_request(
                request=request,
                selected_family=selected_family,
                generated_query=generated_query,
            )
            return await family_service.run(family_request), None
        except Exception as exc:
            return (
                self._failed_family_result(
                    selected_family=selected_family,
                    generated_query=generated_query,
                    error_info=str(exc),
                ),
                "tool_error",
            )

    def _build_family_request(
        self,
        *,
        request: ToolExecutionLayerRequest,
        selected_family: FamilyName,
        generated_query: str,
    ) -> Any:
        freshness_requirement = self._freshness_requirement(request)
        if selected_family == FamilyName.DOCS_SEARCH:
            return DocsSearchFamilyRequest(
                query_text=generated_query,
                target_problem=request.target_problem,
                freshness_requirement=freshness_requirement,
                sub_source_types=request.source_names,
                max_search_results=request.max_search_results,
                preferred_tool=request.preferred_tool,
            )
        if selected_family == FamilyName.PAPER_SEARCH:
            return PaperSearchFamilyRequest(
                query_text=generated_query,
                max_search_results=request.max_search_results,
                max_content_fetches=request.max_content_fetches,
                preferred_tool=request.preferred_tool,
            )
        if selected_family == FamilyName.WEB_SEARCH:
            return WebSearchFamilyRequest(
                query_text=generated_query,
                target_problem=request.target_problem,
                freshness_requirement=freshness_requirement,
                include_domains=request.include_domains,
                exclude_domains=request.exclude_domains,
                max_search_results=request.max_search_results,
                max_content_fetches=request.max_content_fetches,
                min_score_threshold=request.min_score_threshold,
                preferred_tool=request.preferred_tool,
            )
        if selected_family == FamilyName.RESEARCH_KNOWLEDGE_RECALL:
            return ResearchKnowledgeRecallFamilyRequest(
                owner_user_id=request.owner_user_id or "",
                query_text=generated_query,
                query_embedding=request.query_embedding,
                project_scope_id=request.project_scope_id,
                allowed_visibility_scopes=request.allowed_visibility_scopes,
                knowledge_types=request.knowledge_types,
                topic_tags=request.topic_tags,
                source_types=request.source_types,
                limit=request.memory_recall_limit,
                preferred_tool=request.preferred_tool,
            )
        raise ValueError(f"Unsupported selected family '{selected_family}'.")

    def _freshness_requirement(
        self,
        request: ToolExecutionLayerRequest,
    ) -> str | None:
        if request.evidence_shape is None:
            return None
        return request.evidence_shape.freshness_requirement

    def _failed_family_result(
        self,
        *,
        selected_family: FamilyName,
        generated_query: str,
        error_info: str,
    ) -> BaseFamilyExecutionResult:
        return BaseFamilyExecutionResult(
            normalized_items=[],
            acquisition_status=AcquisitionStatus.FAILED,
            dropped_item_count=0,
            source_summary=RetrievalSourceSummary(
                selected_family=selected_family,
                selected_tool=None,
                normalized_count=0,
            ),
            execution_summary=RetrievalExecutionSummary(
                normalized_count=0,
                observability={"family_exception": error_info},
            ),
            retrieval_trace=RetrievalTrace(
                selected_family=selected_family,
                selected_tool=None,
                generated_query=generated_query,
                errors={"family_exception": error_info},
            ),
            error_info=error_info,
            selected_family=selected_family,
            candidate_tools=[],
            selected_tool=None,
        )

    async def _evaluate_completion(
        self,
        *,
        request: ToolExecutionLayerRequest,
        selected_family: FamilyName,
        generated_query: str,
        family_result: BaseFamilyExecutionResult,
        failure_reason: str | None,
        retry_count: int,
        fallback_applied: bool,
        available_families: list[FamilyName],
        blocked_families: list[FamilyName],
    ) -> RequestCompletionEvaluationResult:
        return await self._completion_evaluation_service.evaluate(
            RequestCompletionEvaluationRequest(
                target_problem=request.target_problem,
                selected_family=selected_family,
                generated_query=generated_query,
                execution_outcome=family_result,
                failure_reason=failure_reason,
                continuation_available=False,
                retry_budget=request.retry_budget,
                retry_count=retry_count,
                fallback_policy=request.fallback_policy,
                fallback_applied=fallback_applied,
                max_results=None,
                timeout_limit_ms=request.timeout_limit_ms,
                request_elapsed_ms=None,
                available_families=available_families,
                allowed_source_families=request.allowed_source_families,
                blocked_source_families=normalize_family_list(
                    [*request.blocked_source_families, *blocked_families]
                ),
            )
        )

    def _attempt_trace(
        self,
        *,
        selected_family: FamilyName,
        selected_tool: str | None,
        query_generation_result: RetrievalQueryGenerationResult,
        family_result: BaseFamilyExecutionResult,
        evaluation_result: RequestCompletionEvaluationResult,
        execution_failure_reason: str | None,
        retry_count: int,
        fallback_applied: bool,
    ) -> dict[str, Any]:
        return {
            "selected_family": selected_family,
            "selected_tool": selected_tool,
            "generated_query": query_generation_result.generated_query,
            "query_focus": query_generation_result.query_focus,
            "acquisition_status": family_result.acquisition_status,
            "evaluation_status": evaluation_result.evaluation_status,
            "recovery_action": evaluation_result.recovery_action,
            "next_step_hint": evaluation_result.next_step_hint,
            "retry_count": retry_count,
            "fallback_applied": fallback_applied,
            **self._attempt_diagnostic_fields(
                family_result=family_result,
                execution_failure_reason=execution_failure_reason,
            ),
        }

    def _attempt_diagnostic_fields(
        self,
        *,
        family_result: BaseFamilyExecutionResult,
        execution_failure_reason: str | None,
    ) -> dict[str, Any]:
        observability = family_result.retrieval_trace.observability
        trace_errors = family_result.retrieval_trace.errors
        attempt_error_info = (
            family_result.error_info
            or observability.get("attempt_error_info")
            or next(
                (
                    value
                    for value in trace_errors.values()
                    if isinstance(value, str) and value.strip()
                ),
                None,
            )
        )
        failure_reason = observability.get("failure_reason") or execution_failure_reason
        error_category = observability.get("error_category")
        if (
            family_result.acquisition_status == AcquisitionStatus.FAILED
            and failure_reason is None
        ):
            failure_reason = "unknown_error"
        if (
            family_result.acquisition_status == AcquisitionStatus.FAILED
            and error_category is None
        ):
            error_category = "unknown_error"

        return {
            key: value
            for key, value in {
                "failure_stage": observability.get("failure_stage"),
                "failure_reason": failure_reason,
                "error_category": error_category,
                "attempt_error_info": (
                    sanitize_sensitive_text(attempt_error_info, max_length=500)
                    if attempt_error_info is not None
                    else None
                ),
                "provider_http_status": observability.get(
                    "provider_http_status"
                ),
                "retryable": observability.get("retryable"),
                "exception_type": observability.get("exception_type"),
            }.items()
            if value is not None
        }

    def _completed_result(
        self,
        *,
        request: ToolExecutionLayerRequest,
        family_selection_result: FamilySelectionResult | None,
        query_generation_result: RetrievalQueryGenerationResult | None,
        family_execution_result: BaseFamilyExecutionResult,
        completion_evaluation_result: RequestCompletionEvaluationResult | None,
        retry_count: int,
        fallback_applied: bool,
        recovery_attempt_count: int,
        attempts: list[dict[str, Any]],
        recovery_exhausted_reason: str | None,
    ) -> ToolExecutionLayerResult:
        return self._result(
            request=request,
            execution_status="completed",
            acquisition_status=family_execution_result.acquisition_status,
            family_selection_result=family_selection_result,
            query_generation_result=query_generation_result,
            family_execution_result=family_execution_result,
            completion_evaluation_result=completion_evaluation_result,
            retry_count=retry_count,
            fallback_applied=fallback_applied,
            recovery_attempt_count=recovery_attempt_count,
            attempts=attempts,
            error_info=None,
            recovery_exhausted_reason=recovery_exhausted_reason,
        )

    def _failed_result(
        self,
        *,
        request: ToolExecutionLayerRequest,
        family_selection_result: FamilySelectionResult | None,
        query_generation_result: RetrievalQueryGenerationResult | None,
        family_execution_result: BaseFamilyExecutionResult | None,
        completion_evaluation_result: RequestCompletionEvaluationResult | None,
        retry_count: int,
        fallback_applied: bool,
        recovery_attempt_count: int,
        attempts: list[dict[str, Any]],
        error_info: str,
        recovery_exhausted_reason: str | None,
    ) -> ToolExecutionLayerResult:
        return self._result(
            request=request,
            execution_status="failed",
            acquisition_status=AcquisitionStatus.FAILED,
            family_selection_result=family_selection_result,
            query_generation_result=query_generation_result,
            family_execution_result=family_execution_result,
            completion_evaluation_result=completion_evaluation_result,
            retry_count=retry_count,
            fallback_applied=fallback_applied,
            recovery_attempt_count=recovery_attempt_count,
            attempts=attempts,
            error_info=error_info,
            recovery_exhausted_reason=recovery_exhausted_reason,
        )

    def _result(
        self,
        *,
        request: ToolExecutionLayerRequest,
        execution_status: str,
        acquisition_status: AcquisitionStatus,
        family_selection_result: FamilySelectionResult | None,
        query_generation_result: RetrievalQueryGenerationResult | None,
        family_execution_result: BaseFamilyExecutionResult | None,
        completion_evaluation_result: RequestCompletionEvaluationResult | None,
        retry_count: int,
        fallback_applied: bool,
        recovery_attempt_count: int,
        attempts: list[dict[str, Any]],
        error_info: str | None,
        recovery_exhausted_reason: str | None,
    ) -> ToolExecutionLayerResult:
        source_summary_data = (
            family_execution_result.source_summary.to_legacy_dict()
            if family_execution_result is not None
            else {}
        )
        execution_summary_data = (
            family_execution_result.execution_summary.to_legacy_dict()
            if family_execution_result is not None
            else {}
        )
        retrieval_trace_data = (
            family_execution_result.retrieval_trace.to_legacy_dict()
            if family_execution_result is not None
            else {}
        )
        selected_family = (
            family_execution_result.selected_family
            if family_execution_result is not None
            else family_selection_result.selected_family
            if family_selection_result is not None
            else None
        )
        generated_query = (
            query_generation_result.generated_query
            if query_generation_result is not None
            else None
        )

        source_summary_data["selected_family"] = selected_family
        source_summary_data["normalized_count"] = (
            len(family_execution_result.normalized_items)
            if family_execution_result is not None
            else 0
        )
        execution_summary_data.update(
            {
                "policy": self._POLICY_NAME,
                "execution_status": execution_status,
                "family_selection_status": (
                    family_selection_result.selection_status
                    if family_selection_result is not None
                    else None
                ),
                "query_generation_status": (
                    query_generation_result.generation_status
                    if query_generation_result is not None
                    else None
                ),
                "evaluation_status": (
                    completion_evaluation_result.evaluation_status
                    if completion_evaluation_result is not None
                    else None
                ),
                "request_completion_status": (
                    completion_evaluation_result.request_completion_status
                    if completion_evaluation_result is not None
                    else None
                ),
                "needs_recovery": (
                    completion_evaluation_result.needs_recovery
                    if completion_evaluation_result is not None
                    else False
                ),
                "recovery_action": (
                    completion_evaluation_result.recovery_action
                    if completion_evaluation_result is not None
                    else None
                ),
                "next_step_hint": (
                    completion_evaluation_result.next_step_hint
                    if completion_evaluation_result is not None
                    else None
                ),
                "retry_count": retry_count,
                "fallback_applied": fallback_applied,
                "recovery_attempt_count": recovery_attempt_count,
                "recovery_exhausted_reason": recovery_exhausted_reason,
            }
        )
        retrieval_trace_data.update(
            {
                "target_problem": request.target_problem,
                "selected_family": selected_family,
                "generated_query": generated_query,
                "query_focus": (
                    query_generation_result.query_focus
                    if query_generation_result is not None
                    else None
                ),
                "acquisition_status": acquisition_status,
                "attempts": attempts,
                "retry_count": retry_count,
                "fallback_applied": fallback_applied,
                "recovery_exhausted_reason": recovery_exhausted_reason,
                "family_selection_summary": (
                    family_selection_result.selection_summary
                    if family_selection_result is not None
                    else None
                ),
                "query_generation_summary": (
                    query_generation_result.generation_summary
                    if query_generation_result is not None
                    else None
                ),
                "completion_evaluation_summary": (
                    completion_evaluation_result.evaluation_summary
                    if completion_evaluation_result is not None
                    else None
                ),
            }
        )
        source_summary = RetrievalSourceSummary.model_validate(source_summary_data)
        execution_summary = RetrievalExecutionSummary.model_validate(execution_summary_data)
        retrieval_trace = RetrievalTrace.model_validate(retrieval_trace_data)

        return ToolExecutionLayerResult(
            execution_status=execution_status,
            normalized_items=(
                family_execution_result.normalized_items
                if family_execution_result is not None
                else []
            ),
            acquisition_status=acquisition_status,
            dropped_item_count=(
                family_execution_result.dropped_item_count
                if family_execution_result is not None
                else 0
            ),
            source_summary=source_summary,
            execution_summary=execution_summary,
            retrieval_trace=retrieval_trace,
            error_info=error_info,
        )
