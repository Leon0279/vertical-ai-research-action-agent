"""Tool Execution Layer service tests."""

from __future__ import annotations

import asyncio
from typing import Any

from app.domain.enums import AcquisitionStatus

from app.domain.models import (
    BaseFamilyExecutionResult,
    EvidenceShape,
    FamilySelectionRequest,
    FamilySelectionResult,
    RequestCompletionEvaluationRequest,
    RequestCompletionEvaluationResult,
    RetrievalExecutionSummary,
    RetrievalQueryGenerationRequest,
    RetrievalQueryGenerationResult,
    RetrievalSourceSummary,
    RetrievalTrace,
    ToolExecutionLayerRequest,
)
from app.services.tool_execution_layer.tool_execution_layer_service import (
    ToolExecutionLayerService,
)


class FakeFamilySelectionService:
    def __init__(self, results: list[FamilySelectionResult] | None = None) -> None:
        self.results = results or []
        self.requests: list[FamilySelectionRequest] = []

    async def select_family(self, request: FamilySelectionRequest) -> FamilySelectionResult:
        self.requests.append(request)
        if self.results:
            return self.results.pop(0)
        selected_family = request.available_families[0] if request.available_families else None
        return FamilySelectionResult(
            candidate_families=request.available_families,
            ranked_candidate_families=request.available_families,
            selected_family=selected_family,
            selection_status="selected" if selected_family else "no_match",
            selection_summary={},
            selection_trace={},
            error_info=None if selected_family else "No family matched.",
        )


class FakeQueryGenerationService:
    def __init__(
        self,
        results: list[RetrievalQueryGenerationResult] | None = None,
    ) -> None:
        self.results = results or []
        self.requests: list[RetrievalQueryGenerationRequest] = []

    async def generate_query(
        self,
        request: RetrievalQueryGenerationRequest,
    ) -> RetrievalQueryGenerationResult:
        self.requests.append(request)
        if self.results:
            return self.results.pop(0)
        return _query_result(request.selected_family, f"{request.selected_family} query")


class FakeCompletionEvaluationService:
    def __init__(
        self,
        results: list[RequestCompletionEvaluationResult] | None = None,
    ) -> None:
        self.results = results or []
        self.requests: list[RequestCompletionEvaluationRequest] = []

    async def evaluate(
        self,
        request: RequestCompletionEvaluationRequest,
    ) -> RequestCompletionEvaluationResult:
        self.requests.append(request)
        if self.results:
            return self.results.pop(0)
        return _evaluation_result("stop", "none", request_completed=True)


class FakeFamilyService:
    def __init__(
        self,
        *,
        selected_family: str,
        results: list[BaseFamilyExecutionResult] | None = None,
        raises: Exception | None = None,
    ) -> None:
        self.selected_family = selected_family
        self.results = results or []
        self.raises = raises
        self.requests: list[Any] = []

    async def run(self, request: Any) -> BaseFamilyExecutionResult:
        self.requests.append(request)
        if self.raises is not None:
            raise self.raises
        if self.results:
            return self.results.pop(0)
        return _family_result(self.selected_family, acquisition_status=AcquisitionStatus.SUCCESS)


def _execute(service: ToolExecutionLayerService, request: ToolExecutionLayerRequest):
    return asyncio.run(service.execute(request))


def _service(
    *,
    selector: FakeFamilySelectionService | None = None,
    query: FakeQueryGenerationService | None = None,
    evaluator: FakeCompletionEvaluationService | None = None,
    docs: FakeFamilyService | None = None,
    paper: FakeFamilyService | None = None,
    web: FakeFamilyService | None = None,
    memory: FakeFamilyService | None = None,
) -> ToolExecutionLayerService:
    return ToolExecutionLayerService(
        family_selection_service=selector or FakeFamilySelectionService(),
        query_generation_service=query or FakeQueryGenerationService(),
        completion_evaluation_service=evaluator or FakeCompletionEvaluationService(),
        docs_search_family_service=docs,
        paper_search_family_service=paper,
        web_search_family_service=web,
        research_knowledge_recall_family_service=memory,
    )


def _selection_result(
    selected_family: str | None,
    *,
    status: str = "selected",
    error_info: str | None = None,
) -> FamilySelectionResult:
    return FamilySelectionResult(
        candidate_families=[selected_family] if selected_family else [],
        ranked_candidate_families=[selected_family] if selected_family else [],
        selected_family=selected_family,
        selection_status=status,
        selection_summary={},
        selection_trace={},
        error_info=error_info,
    )


def _query_result(
    selected_family: str,
    generated_query: str | None,
    *,
    status: str = "succeeded",
) -> RetrievalQueryGenerationResult:
    return RetrievalQueryGenerationResult(
        selected_family=selected_family,
        generated_query=generated_query,
        query_focus="focus" if generated_query else None,
        preserved_terms=[],
        generation_status=status,
        generation_summary={},
        generation_trace={},
        error_info=None if status == "succeeded" else "query failed",
    )


def _item(item_id: str = "1") -> dict[str, Any]:
    return {
        "item_id": item_id,
        "source_family": "docs_search",
        "source_references": [
            {
                "source_type": "document",
                "source_id": f"doc-{item_id}",
            }
        ],
        "content": "Useful content",
    }


def _family_result(
    selected_family: str,
    *,
    acquisition_status: AcquisitionStatus,
    selected_tool: str | None = "tool_v1",
    normalized_items: list[dict[str, Any]] | None = None,
) -> BaseFamilyExecutionResult:
    return BaseFamilyExecutionResult(
        normalized_items=normalized_items or [_item()],
        acquisition_status=acquisition_status,
        dropped_item_count=0,
        source_summary=RetrievalSourceSummary(
            selected_family=selected_family,
            selected_tool=selected_tool,
        ),
        execution_summary=RetrievalExecutionSummary(),
        retrieval_trace=RetrievalTrace(),
        error_info=None if acquisition_status != AcquisitionStatus.FAILED else "family failed",
        selected_family=selected_family,
        candidate_tools=[selected_tool] if selected_tool else [],
        selected_tool=selected_tool,
    )


def _evaluation_result(
    recovery_action: str,
    next_step_hint: str,
    *,
    request_completed: bool = False,
    status: str = "evaluated",
) -> RequestCompletionEvaluationResult:
    return RequestCompletionEvaluationResult(
        evaluation_status=status,
        request_completion_status="complete" if request_completed else "incomplete_recoverable",
        request_completed=request_completed,
        needs_recovery=not request_completed,
        recovery_action=recovery_action if status == "evaluated" else None,
        recovery_reason="reason",
        next_step_hint=next_step_hint if status == "evaluated" else None,
        evaluation_summary={},
        evaluation_trace={},
        error_info=None if status == "evaluated" else "evaluation failed",
    )


def test_happy_path_executes_docs_and_stops() -> None:
    selector = FakeFamilySelectionService([_selection_result("docs_search")])
    docs = FakeFamilyService(selected_family="docs_search")
    service = _service(selector=selector, docs=docs)

    result = _execute(
        service,
        ToolExecutionLayerRequest(target_problem="Find official docs"),
    )

    assert result.execution_status == "completed"
    assert result.acquisition_status == AcquisitionStatus.SUCCESS
    assert result.normalized_items == [{"item_id": "1"}]
    assert result.retrieval_trace["selected_family"] == "docs_search"
    assert result.retrieval_trace["generated_query"] == "docs_search query"
    assert result.retrieval_trace["query_focus"] == "focus"
    assert "selected_tool" not in result.model_dump().keys()
    assert "selected_family" not in result.model_dump().keys()
    assert "generated_query" not in result.model_dump().keys()
    assert "query_focus" not in result.model_dump().keys()
    assert "family_selection_result" not in result.model_dump().keys()
    assert "query_generation_result" not in result.model_dump().keys()
    assert "family_execution_result" not in result.model_dump().keys()
    assert "completion_evaluation_result" not in result.model_dump().keys()
    assert len(docs.requests) == 1


def test_preferred_tool_is_passed_through_but_not_synthesized() -> None:
    selector = FakeFamilySelectionService([_selection_result("docs_search")])
    docs = FakeFamilyService(selected_family="docs_search")
    service = _service(selector=selector, docs=docs)

    result = _execute(
        service,
        ToolExecutionLayerRequest(
            target_problem="Find official docs",
            preferred_tool="research_executor_tool_hint",
        ),
    )

    assert result.execution_status == "completed"
    assert docs.requests[0].preferred_tool == "research_executor_tool_hint"
    assert result.source_summary["selected_tool"] == "tool_v1"


def test_family_selection_no_match_stops_before_query_generation() -> None:
    selector = FakeFamilySelectionService(
        [_selection_result(None, status="no_match", error_info="no match")]
    )
    query = FakeQueryGenerationService()
    docs = FakeFamilyService(selected_family="docs_search")
    service = _service(selector=selector, query=query, docs=docs)

    result = _execute(
        service,
        ToolExecutionLayerRequest(target_problem="Find official docs"),
    )

    assert result.execution_status == "failed"
    assert result.error_info == "no match"
    assert query.requests == []
    assert docs.requests == []


def test_query_generation_failed_stops_before_family_execution() -> None:
    selector = FakeFamilySelectionService([_selection_result("docs_search")])
    query = FakeQueryGenerationService(
        [_query_result("docs_search", None, status="failed")]
    )
    docs = FakeFamilyService(selected_family="docs_search")
    service = _service(selector=selector, query=query, docs=docs)

    result = _execute(
        service,
        ToolExecutionLayerRequest(target_problem="Find official docs"),
    )

    assert result.execution_status == "failed"
    assert result.error_info == "query failed"
    assert docs.requests == []


def test_missing_selected_family_service_returns_failed() -> None:
    selector = FakeFamilySelectionService([_selection_result("web_search")])
    service = _service(selector=selector)

    result = _execute(
        service,
        ToolExecutionLayerRequest(target_problem="Find latest web info"),
    )

    assert result.execution_status == "failed"
    assert result.error_info == "No family service registered for selected family 'web_search'."


def test_memory_selected_without_owner_user_id_returns_failed() -> None:
    selector = FakeFamilySelectionService([_selection_result("research_knowledge_recall")])
    memory = FakeFamilyService(selected_family="research_knowledge_recall")
    service = _service(selector=selector, memory=memory)

    result = _execute(
        service,
        ToolExecutionLayerRequest(
            target_problem="Recall prior knowledge",
            action_mode="memory_backed_acquisition",
        ),
    )

    assert result.execution_status == "failed"
    assert result.error_info == "owner_user_id is required for research_knowledge_recall family."
    assert memory.requests == []


def test_retry_same_tool_reuses_same_family_query_and_original_preferred_tool() -> None:
    selector = FakeFamilySelectionService([_selection_result("docs_search")])
    query = FakeQueryGenerationService([
        _query_result("docs_search", "original query"),
    ])
    evaluator = FakeCompletionEvaluationService(
        [
            _evaluation_result("retry_same_tool", "retry_same_tool"),
            _evaluation_result("stop", "none", request_completed=True),
        ]
    )
    docs = FakeFamilyService(
        selected_family="docs_search",
        results=[
            _family_result("docs_search", acquisition_status=AcquisitionStatus.FAILED, selected_tool="tool_from_family"),
            _family_result("docs_search", acquisition_status=AcquisitionStatus.SUCCESS, selected_tool="tool_from_family"),
        ],
    )
    service = _service(selector=selector, query=query, evaluator=evaluator, docs=docs)

    result = _execute(
        service,
        ToolExecutionLayerRequest(
            target_problem="Find official docs",
            preferred_tool="executor_hint",
            retry_budget=1,
        ),
    )

    assert result.execution_status == "completed"
    assert result.execution_summary["retry_count"] == 1
    assert result.execution_summary["recovery_attempt_count"] == 1
    assert len(selector.requests) == 1
    assert len(query.requests) == 1
    assert len(docs.requests) == 2
    assert docs.requests[0].query_text == "original query"
    assert docs.requests[1].query_text == "original query"
    assert docs.requests[0].preferred_tool == "executor_hint"
    assert docs.requests[1].preferred_tool == "executor_hint"


def test_broader_fallback_blocks_current_family_and_executes_new_family() -> None:
    selector = FakeFamilySelectionService(
        [_selection_result("docs_search"), _selection_result("web_search")]
    )
    query = FakeQueryGenerationService(
        [
            _query_result("docs_search", "docs query"),
            _query_result("web_search", "web query"),
        ]
    )
    evaluator = FakeCompletionEvaluationService(
        [
            _evaluation_result("fallback", "fallback_to_broader_search"),
            _evaluation_result("stop", "none", request_completed=True),
        ]
    )
    docs = FakeFamilyService(
        selected_family="docs_search",
        results=[_family_result("docs_search", acquisition_status=AcquisitionStatus.NO_RESULT)],
    )
    web = FakeFamilyService(
        selected_family="web_search",
        results=[_family_result("web_search", acquisition_status=AcquisitionStatus.SUCCESS)],
    )
    service = _service(selector=selector, query=query, evaluator=evaluator, docs=docs, web=web)

    result = _execute(
        service,
        ToolExecutionLayerRequest(
            target_problem="Find current public info",
            fallback_policy="fallback_to_broader_search",
        ),
    )

    assert result.execution_status == "completed"
    assert result.retrieval_trace["selected_family"] == "web_search"
    assert result.retrieval_trace["generated_query"] == "web query"
    assert result.execution_summary["fallback_applied"] is True
    assert result.execution_summary["recovery_attempt_count"] == 1
    assert selector.requests[1].blocked_source_families == ["docs_search"]
    assert docs.requests[0].query_text == "docs query"
    assert web.requests[0].query_text == "web query"


def test_same_family_fallback_is_recorded_as_unavailable() -> None:
    selector = FakeFamilySelectionService([_selection_result("docs_search")])
    evaluator = FakeCompletionEvaluationService(
        [_evaluation_result("fallback", "fallback_within_same_family")]
    )
    docs = FakeFamilyService(
        selected_family="docs_search",
        results=[_family_result("docs_search", acquisition_status=AcquisitionStatus.NO_RESULT)],
    )
    service = _service(selector=selector, evaluator=evaluator, docs=docs)

    result = _execute(
        service,
        ToolExecutionLayerRequest(target_problem="Find official docs"),
    )

    assert result.execution_status == "completed"
    assert result.execution_summary["needs_recovery"] is True
    assert result.execution_summary["recovery_exhausted_reason"] == (
        "same_family_fallback_not_executable"
    )


def test_family_exception_is_evaluated_as_tool_error() -> None:
    selector = FakeFamilySelectionService([_selection_result("docs_search")])
    evaluator = FakeCompletionEvaluationService(
        [_evaluation_result("stop", "stop_request")]
    )
    docs = FakeFamilyService(
        selected_family="docs_search",
        raises=RuntimeError("family boom"),
    )
    service = _service(selector=selector, evaluator=evaluator, docs=docs)

    result = _execute(
        service,
        ToolExecutionLayerRequest(target_problem="Find official docs"),
    )

    assert result.execution_status == "completed"
    assert result.acquisition_status == AcquisitionStatus.FAILED
    assert evaluator.requests[0].failure_reason == "tool_error"
    assert result.retrieval_trace["family_exception"] == "family boom"


def test_evaluation_failed_returns_failed_with_family_result() -> None:
    selector = FakeFamilySelectionService([_selection_result("docs_search")])
    evaluator = FakeCompletionEvaluationService(
        [_evaluation_result("stop", "none", status="failed")]
    )
    docs = FakeFamilyService(selected_family="docs_search")
    service = _service(selector=selector, evaluator=evaluator, docs=docs)

    result = _execute(
        service,
        ToolExecutionLayerRequest(target_problem="Find official docs"),
    )

    assert result.execution_status == "failed"
    assert result.error_info == "evaluation failed"
    assert result.normalized_items == [{"item_id": "1"}]


def test_family_request_mapping_for_all_families() -> None:
    docs = FakeFamilyService(selected_family="docs_search")
    paper = FakeFamilyService(selected_family="paper_search")
    web = FakeFamilyService(selected_family="web_search")
    memory = FakeFamilyService(selected_family="research_knowledge_recall")

    for selected_family, family_service in [
        ("docs_search", docs),
        ("paper_search", paper),
        ("web_search", web),
        ("research_knowledge_recall", memory),
    ]:
        selector = FakeFamilySelectionService([_selection_result(selected_family)])
        service = _service(
            selector=selector,
            docs=docs,
            paper=paper,
            web=web,
            memory=memory,
        )
        _execute(
            service,
            ToolExecutionLayerRequest(
                target_problem="Map request",
                preferred_tool="executor_tool",
                evidence_shape=EvidenceShape(freshness_requirement="fresh_required"),
                source_names=["docs"],
                include_domains=["example.com"],
                exclude_domains=["bad.example"],
                max_search_results=7,
                max_content_fetches=2,
                min_score_threshold=0.7,
                owner_user_id="user_1",
                query_embedding=[0.1, 0.2],
                project_scope_id="project_1",
                allowed_visibility_scopes=["user", "project"],
                knowledge_types=["finding"],
                topic_tags=["rag"],
                source_types=["paper"],
                memory_recall_limit=4,
            ),
        )

    assert docs.requests[-1].sub_source_types == ["docs"]
    assert docs.requests[-1].freshness_requirement == "fresh_required"
    assert docs.requests[-1].max_search_results == 7
    assert paper.requests[-1].max_content_fetches == 2
    assert web.requests[-1].include_domains == ["example.com"]
    assert web.requests[-1].exclude_domains == ["bad.example"]
    assert web.requests[-1].min_score_threshold == 0.7
    assert memory.requests[-1].owner_user_id == "user_1"
    assert memory.requests[-1].query_embedding == [0.1, 0.2]
    assert memory.requests[-1].limit == 4
    assert memory.requests[-1].preferred_tool == "executor_tool"
