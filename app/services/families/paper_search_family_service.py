"""Family-level service for paper search retrieval execution."""

from __future__ import annotations

from app.domain.enums import AcquisitionStatus, FamilyName
from app.domain.models import (
    ArxivPaperSearchToolRequest,
    ArxivPaperSearchToolResult,
    PaperSearchFamilyRequest,
    PaperSearchFamilyResult,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)
from app.services.families.contracts.paper_search_family_service_protocol import (
    PaperSearchFamilyServiceProtocol,
)
from app.services.tools.contracts.arxiv_paper_search_tool_protocol import (
    ArxivPaperSearchToolProtocol,
)


class PaperSearchFamilyService(PaperSearchFamilyServiceProtocol):
    """Resolve a paper_search family request to a concrete paper tool."""

    _FAMILY_NAME = FamilyName.PAPER_SEARCH
    _DEFAULT_TOOL_ID = "arxiv_paper_search_v1"

    def __init__(self, arxiv_paper_search_tool: ArxivPaperSearchToolProtocol | None) -> None:
        self._tool_registry: dict[str, ArxivPaperSearchToolProtocol] = {}
        if arxiv_paper_search_tool is not None:
            self._tool_registry[self._DEFAULT_TOOL_ID] = arxiv_paper_search_tool

    async def run(self, request: PaperSearchFamilyRequest) -> PaperSearchFamilyResult:
        """Select a paper_search tool, execute it, and return a family-level result."""

        normalized_request = self._normalize_request(request)
        candidate_tools = list(self._tool_registry)

        if not candidate_tools:
            return self._failed_result(
                normalized_request=normalized_request,
                candidate_tools=[],
                selected_tool=None,
                error_info="No available tools registered for paper_search family.",
            )

        selected_tool = self._select_tool(normalized_request, candidate_tools)
        if selected_tool is None:
            return self._failed_result(
                normalized_request=normalized_request,
                candidate_tools=candidate_tools,
                selected_tool=None,
                error_info=(
                    f"Preferred tool '{normalized_request.preferred_tool}' is not available in "
                    "paper_search family."
                ),
            )

        tool = self._tool_registry[selected_tool]
        tool_result = await tool.run(
            ArxivPaperSearchToolRequest(
                query_text=normalized_request.query_text,
                max_search_results=normalized_request.max_search_results,
                max_content_fetches=normalized_request.max_content_fetches,
            )
        )
        return self._wrap_tool_result(
            normalized_request=normalized_request,
            candidate_tools=candidate_tools,
            selected_tool=selected_tool,
            tool_result=tool_result,
        )

    def _normalize_request(self, request: PaperSearchFamilyRequest) -> PaperSearchFamilyRequest:
        return PaperSearchFamilyRequest(
            query_text=request.query_text.strip(),
            max_search_results=request.max_search_results,
            max_content_fetches=request.max_content_fetches,
            preferred_tool=(request.preferred_tool or "").strip() or None,
        )

    def _select_tool(
        self,
        request: PaperSearchFamilyRequest,
        candidate_tools: list[str],
    ) -> str | None:
        if request.preferred_tool is None:
            return self._DEFAULT_TOOL_ID if self._DEFAULT_TOOL_ID in candidate_tools else None
        if request.preferred_tool in candidate_tools:
            return request.preferred_tool
        return None

    def _wrap_tool_result(
        self,
        *,
        normalized_request: PaperSearchFamilyRequest,
        candidate_tools: list[str],
        selected_tool: str,
        tool_result: ArxivPaperSearchToolResult,
    ) -> PaperSearchFamilyResult:
        source_summary = tool_result.source_summary.model_copy(
            update={
                "selected_family": self._FAMILY_NAME,
                "selected_tool": selected_tool,
            }
        )

        execution_summary = tool_result.execution_summary.model_copy(
            update={
                "metrics": {
                    **tool_result.execution_summary.metrics,
                    "candidate_tool_count": len(candidate_tools),
                },
                "observability": {
                    **tool_result.execution_summary.observability,
                    "preferred_tool_requested": normalized_request.preferred_tool,
                },
            }
        )

        retrieval_trace = tool_result.retrieval_trace.model_copy(
            update={
                "selected_family": self._FAMILY_NAME,
                "selected_tool": selected_tool,
                "context": {
                    **tool_result.retrieval_trace.context,
                    "candidate_tools": candidate_tools,
                    "preferred_tool": normalized_request.preferred_tool,
                },
            }
        )

        return PaperSearchFamilyResult(
            normalized_items=tool_result.normalized_items,
            acquisition_status=tool_result.acquisition_status,
            dropped_item_count=tool_result.dropped_item_count,
            source_summary=source_summary,
            execution_summary=execution_summary,
            retrieval_trace=retrieval_trace,
            error_info=tool_result.error_info,
            selected_family=self._FAMILY_NAME,
            candidate_tools=candidate_tools,
            selected_tool=selected_tool,
        )

    def _failed_result(
        self,
        *,
        normalized_request: PaperSearchFamilyRequest,
        candidate_tools: list[str],
        selected_tool: str | None,
        error_info: str,
    ) -> PaperSearchFamilyResult:
        return PaperSearchFamilyResult(
            normalized_items=[],
            acquisition_status=AcquisitionStatus.FAILED,
            dropped_item_count=0,
            source_summary=RetrievalSourceSummary(
                selected_family=self._FAMILY_NAME,
                selected_tool=selected_tool,
                normalized_count=0,
            ),
            execution_summary=RetrievalExecutionSummary(
                normalized_count=0,
                metrics={"candidate_tool_count": len(candidate_tools)},
                observability={"preferred_tool_requested": normalized_request.preferred_tool},
            ),
            retrieval_trace=RetrievalTrace(
                selected_family=self._FAMILY_NAME,
                selected_tool=selected_tool,
                context={
                    "candidate_tools": candidate_tools,
                    "preferred_tool": normalized_request.preferred_tool,
                    "query_text": normalized_request.query_text,
                },
                errors={"family_error": error_info},
            ),
            error_info=error_info,
            selected_family=self._FAMILY_NAME,
            candidate_tools=candidate_tools,
            selected_tool=selected_tool,
        )
