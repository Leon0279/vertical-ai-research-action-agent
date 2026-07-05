"""Tool Execution Layer coordination service."""

from __future__ import annotations

from typing import Any

from app.domain.enums import AcquisitionStatus
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


class ToolExecutionLayerService(ToolExecutionLayerServiceProtocol):
    """Coordinate one bounded Tool Execution Layer request for Research Executor."""

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
            "docs_search": docs_search_family_service,
            "paper_search": paper_search_family_service,
            "web_search": web_search_family_service,
            "research_knowledge_recall": research_knowledge_recall_family_service,
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

        blocked_families = list(normalized_request.blocked_source_families)
        attempts: list[dict[str, Any]] = []
        latest_selection: FamilySelectionResult | None = None
        latest_query_generation: RetrievalQueryGenerationResult | None = None
        latest_family_result: BaseFamilyExecutionResult | None = None
        latest_evaluation: RequestCompletionEvaluationResult | None = None
        retry_count = 0
        fallback_applied = False
        recovery_attempt_count = 0
        recovery_exhausted_reason: str | None = None
        retry_family: str | None = None
        retry_query_generation: RetrievalQueryGenerationResult | None = None

        while True:
            if retry_family is None:
                selection_result = await self._select_family(
                    request=normalized_request,
                    available_families=effective_available_families,
                    blocked_families=blocked_families,
                )
                latest_selection = selection_result
                if (
                    selection_result.selection_status != "selected"
                    or not selection_result.selected_family
                ):
                    return self._failed_result(
                        request=normalized_request,
                        family_selection_result=latest_selection,
                        query_generation_result=latest_query_generation,
                        family_execution_result=latest_family_result,
                        completion_evaluation_result=latest_evaluation,
                        retry_count=retry_count,
                        fallback_applied=fallback_applied,
                        recovery_attempt_count=recovery_attempt_count,
                        attempts=attempts,
                        error_info=selection_result.error_info
                        or "No family was selected for Tool Execution Layer request.",
                        recovery_exhausted_reason=recovery_exhausted_reason,
                    )

                selected_family = selection_result.selected_family
                query_generation_result = await self._generate_query(
                    request=normalized_request,
                    selected_family=selected_family,
                )
                latest_query_generation = query_generation_result
            else:
                selected_family = retry_family
                query_generation_result = retry_query_generation
                retry_family = None
                retry_query_generation = None

            if query_generation_result is None:
                return self._failed_result(
                    request=normalized_request,
                    family_selection_result=latest_selection,
                    query_generation_result=latest_query_generation,
                    family_execution_result=latest_family_result,
                    completion_evaluation_result=latest_evaluation,
                    retry_count=retry_count,
                    fallback_applied=fallback_applied,
                    recovery_attempt_count=recovery_attempt_count,
                    attempts=attempts,
                    error_info="Retry requested without a generated query.",
                    recovery_exhausted_reason=recovery_exhausted_reason,
                )

            family_service = self._family_services.get(selected_family)
            if family_service is None:
                return self._failed_result(
                    request=normalized_request,
                    family_selection_result=latest_selection,
                    query_generation_result=latest_query_generation,
                    family_execution_result=latest_family_result,
                    completion_evaluation_result=latest_evaluation,
                    retry_count=retry_count,
                    fallback_applied=fallback_applied,
                    recovery_attempt_count=recovery_attempt_count,
                    attempts=attempts,
                    error_info=f"No family service registered for selected family '{selected_family}'.",
                    recovery_exhausted_reason=recovery_exhausted_reason,
                )

            generated_query = query_generation_result.generated_query
            if (
                query_generation_result.generation_status != "succeeded"
                or not generated_query
            ):
                return self._failed_result(
                    request=normalized_request,
                    family_selection_result=latest_selection,
                    query_generation_result=latest_query_generation,
                    family_execution_result=latest_family_result,
                    completion_evaluation_result=latest_evaluation,
                    retry_count=retry_count,
                    fallback_applied=fallback_applied,
                    recovery_attempt_count=recovery_attempt_count,
                    attempts=attempts,
                    error_info=query_generation_result.error_info
                    or "Query generation did not produce a usable query.",
                    recovery_exhausted_reason=recovery_exhausted_reason,
                )

            if selected_family == "research_knowledge_recall" and not normalized_request.owner_user_id:
                return self._failed_result(
                    request=normalized_request,
                    family_selection_result=latest_selection,
                    query_generation_result=latest_query_generation,
                    family_execution_result=latest_family_result,
                    completion_evaluation_result=latest_evaluation,
                    retry_count=retry_count,
                    fallback_applied=fallback_applied,
                    recovery_attempt_count=recovery_attempt_count,
                    attempts=attempts,
                    error_info="owner_user_id is required for research_knowledge_recall family.",
                    recovery_exhausted_reason=recovery_exhausted_reason,
                )

            family_result, execution_failure_reason = await self._execute_family(
                request=normalized_request,
                selected_family=selected_family,
                generated_query=generated_query,
                family_service=family_service,
            )
            latest_family_result = family_result

            evaluation_result = await self._evaluate_completion(
                request=normalized_request,
                selected_family=selected_family,
                generated_query=generated_query,
                family_result=family_result,
                failure_reason=execution_failure_reason,
                retry_count=retry_count,
                fallback_applied=fallback_applied,
                available_families=effective_available_families,
                blocked_families=blocked_families,
            )
            latest_evaluation = evaluation_result
            if evaluation_result.evaluation_status == "failed":
                return self._failed_result(
                    request=normalized_request,
                    family_selection_result=latest_selection,
                    query_generation_result=latest_query_generation,
                    family_execution_result=latest_family_result,
                    completion_evaluation_result=latest_evaluation,
                    retry_count=retry_count,
                    fallback_applied=fallback_applied,
                    recovery_attempt_count=recovery_attempt_count,
                    attempts=attempts,
                    error_info=evaluation_result.error_info
                    or "Request completion evaluation failed.",
                    recovery_exhausted_reason=recovery_exhausted_reason,
                )

            attempt = self._attempt_trace(
                selected_family=selected_family,
                query_generation_result=query_generation_result,
                family_result=family_result,
                evaluation_result=evaluation_result,
                retry_count=retry_count,
                fallback_applied=fallback_applied,
            )
            attempts.append(attempt)

            if evaluation_result.recovery_action == "stop":
                return self._completed_result(
                    request=normalized_request,
                    family_selection_result=latest_selection,
                    query_generation_result=latest_query_generation,
                    family_execution_result=latest_family_result,
                    completion_evaluation_result=latest_evaluation,
                    retry_count=retry_count,
                    fallback_applied=fallback_applied,
                    recovery_attempt_count=recovery_attempt_count,
                    attempts=attempts,
                    recovery_exhausted_reason=recovery_exhausted_reason,
                )

            if evaluation_result.recovery_action == "retry_same_tool":
                if retry_count >= normalized_request.retry_budget:
                    recovery_exhausted_reason = "retry_budget_exhausted"
                    return self._completed_result(
                        request=normalized_request,
                        family_selection_result=latest_selection,
                        query_generation_result=latest_query_generation,
                        family_execution_result=latest_family_result,
                        completion_evaluation_result=latest_evaluation,
                        retry_count=retry_count,
                        fallback_applied=fallback_applied,
                        recovery_attempt_count=recovery_attempt_count,
                        attempts=attempts,
                        recovery_exhausted_reason=recovery_exhausted_reason,
                    )
                retry_count += 1
                recovery_attempt_count += 1
                retry_family = selected_family
                retry_query_generation = query_generation_result
                continue

            if (
                evaluation_result.recovery_action == "fallback"
                and evaluation_result.next_step_hint == "fallback_to_broader_search"
            ):
                if selected_family not in blocked_families:
                    blocked_families.append(selected_family)
                if fallback_applied:
                    recovery_exhausted_reason = "fallback_already_applied"
                    return self._completed_result(
                        request=normalized_request,
                        family_selection_result=latest_selection,
                        query_generation_result=latest_query_generation,
                        family_execution_result=latest_family_result,
                        completion_evaluation_result=latest_evaluation,
                        retry_count=retry_count,
                        fallback_applied=fallback_applied,
                        recovery_attempt_count=recovery_attempt_count,
                        attempts=attempts,
                        recovery_exhausted_reason=recovery_exhausted_reason,
                    )
                fallback_applied = True
                recovery_attempt_count += 1
                continue

            recovery_exhausted_reason = (
                "same_family_fallback_not_executable"
                if evaluation_result.next_step_hint == "fallback_within_same_family"
                else "continuation_not_supported"
                if evaluation_result.next_step_hint == "continue_current_request"
                else "recovery_action_not_executable"
            )
            return self._completed_result(
                request=normalized_request,
                family_selection_result=latest_selection,
                query_generation_result=latest_query_generation,
                family_execution_result=latest_family_result,
                completion_evaluation_result=latest_evaluation,
                retry_count=retry_count,
                fallback_applied=fallback_applied,
                recovery_attempt_count=recovery_attempt_count,
                attempts=attempts,
                recovery_exhausted_reason=recovery_exhausted_reason,
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
            allowed_source_families=self._normalize_string_list(
                request.allowed_source_families
            ),
            preferred_source_families=self._normalize_string_list(
                request.preferred_source_families
            ),
            blocked_source_families=self._normalize_string_list(
                request.blocked_source_families
            ),
            available_families=self._normalize_string_list(request.available_families),
            success_hint=(request.success_hint or "").strip() or None,
            recent_low_value_queries=self._normalize_string_list(
                request.recent_low_value_queries
            ),
            preferred_tool=(request.preferred_tool or "").strip() or None,
            source_names=self._normalize_string_list(request.source_names),
            include_domains=self._normalize_string_list(request.include_domains),
            exclude_domains=self._normalize_string_list(request.exclude_domains),
            max_search_results=request.max_search_results,
            max_content_fetches=request.max_content_fetches,
            min_score_threshold=request.min_score_threshold,
            owner_user_id=(request.owner_user_id or "").strip() or None,
            query_embedding=request.query_embedding,
            project_scope_id=(request.project_scope_id or "").strip() or None,
            allowed_visibility_scopes=self._normalize_string_list(
                request.allowed_visibility_scopes
            ),
            knowledge_types=self._normalize_string_list(request.knowledge_types),
            topic_tags=self._normalize_string_list(request.topic_tags),
            source_types=self._normalize_string_list(request.source_types),
            memory_recall_limit=request.memory_recall_limit,
            retry_budget=request.retry_budget,
            fallback_policy=request.fallback_policy,
            timeout_limit_ms=request.timeout_limit_ms,
        )

    def _normalize_string_list(self, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stripped = value.strip()
            if not stripped or stripped in seen:
                continue
            normalized.append(stripped)
            seen.add(stripped)
        return normalized

    def _injected_families(self) -> list[str]:
        return [
            family
            for family, service in self._family_services.items()
            if service is not None
        ]

    def _effective_available_families(
        self,
        request: ToolExecutionLayerRequest,
        injected_families: list[str],
    ) -> list[str]:
        if not request.available_families:
            return injected_families
        injected = set(injected_families)
        return [family for family in request.available_families if family in injected]

    async def _select_family(
        self,
        *,
        request: ToolExecutionLayerRequest,
        available_families: list[str],
        blocked_families: list[str],
    ) -> FamilySelectionResult:
        merged_blocked = self._normalize_string_list(
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
        selected_family: str,
    ) -> RetrievalQueryGenerationResult:
        return await self._query_generation_service.generate_query(
            RetrievalQueryGenerationRequest(
                selected_family=selected_family,
                target_problem=request.target_problem,
                evidence_goal=request.evidence_goal,
                evidence_shape=request.evidence_shape,
                success_hint=request.success_hint,
                task_framing=request.task_framing,
                recent_low_value_queries=request.recent_low_value_queries,
            )
        )

    async def _execute_family(
        self,
        *,
        request: ToolExecutionLayerRequest,
        selected_family: str,
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
        selected_family: str,
        generated_query: str,
    ) -> Any:
        freshness_requirement = self._freshness_requirement(request)
        if selected_family == "docs_search":
            return DocsSearchFamilyRequest(
                query_text=generated_query,
                target_problem=request.target_problem,
                freshness_requirement=freshness_requirement,
                sub_source_types=request.source_names,
                max_search_results=request.max_search_results,
                preferred_tool=request.preferred_tool,
            )
        if selected_family == "paper_search":
            return PaperSearchFamilyRequest(
                query_text=generated_query,
                max_search_results=request.max_search_results,
                max_content_fetches=request.max_content_fetches,
                preferred_tool=request.preferred_tool,
            )
        if selected_family == "web_search":
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
        if selected_family == "research_knowledge_recall":
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
        selected_family: str,
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
        selected_family: str,
        generated_query: str,
        family_result: BaseFamilyExecutionResult,
        failure_reason: str | None,
        retry_count: int,
        fallback_applied: bool,
        available_families: list[str],
        blocked_families: list[str],
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
                blocked_source_families=self._normalize_string_list(
                    [*request.blocked_source_families, *blocked_families]
                ),
            )
        )

    def _attempt_trace(
        self,
        *,
        selected_family: str,
        query_generation_result: RetrievalQueryGenerationResult,
        family_result: BaseFamilyExecutionResult,
        evaluation_result: RequestCompletionEvaluationResult,
        retry_count: int,
        fallback_applied: bool,
    ) -> dict[str, Any]:
        return {
            "selected_family": selected_family,
            "generated_query": query_generation_result.generated_query,
            "query_focus": query_generation_result.query_focus,
            "acquisition_status": family_result.acquisition_status,
            "evaluation_status": evaluation_result.evaluation_status,
            "recovery_action": evaluation_result.recovery_action,
            "next_step_hint": evaluation_result.next_step_hint,
            "retry_count": retry_count,
            "fallback_applied": fallback_applied,
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
