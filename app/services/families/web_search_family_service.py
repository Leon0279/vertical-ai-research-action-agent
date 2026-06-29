"""Family-level service for web search retrieval execution."""

from __future__ import annotations

from app.domain.models import (
    TavilyWebSearchToolRequest,
    TavilyWebSearchToolResult,
    WebSearchFamilyRequest,
    WebSearchFamilyResult,
)
from app.services.families.contracts.web_search_family_service_protocol import (
    WebSearchFamilyServiceProtocol,
)
from app.services.tools.contracts.tavily_web_search_tool_protocol import (
    TavilyWebSearchToolProtocol,
)


class WebSearchFamilyService(WebSearchFamilyServiceProtocol):
    """Resolve a web_search family request to a concrete web tool."""

    _FAMILY_NAME = "web_search"
    _DEFAULT_TOOL_ID = "tavily_web_search_v1"

    def __init__(self, tavily_web_search_tool: TavilyWebSearchToolProtocol | None) -> None:
        self._tool_registry: dict[str, TavilyWebSearchToolProtocol] = {}
        if tavily_web_search_tool is not None:
            self._tool_registry[self._DEFAULT_TOOL_ID] = tavily_web_search_tool

    async def run(self, request: WebSearchFamilyRequest) -> WebSearchFamilyResult:
        """Select a web_search tool, execute it, and return a family-level result."""

        normalized_request = self._normalize_request(request)
        candidate_tools = list(self._tool_registry)

        if not candidate_tools:
            return self._failed_result(
                normalized_request=normalized_request,
                candidate_tools=[],
                selected_tool=None,
                error_info="No available tools registered for web_search family.",
            )

        selected_tool = self._select_tool(normalized_request, candidate_tools)
        if selected_tool is None:
            return self._failed_result(
                normalized_request=normalized_request,
                candidate_tools=candidate_tools,
                selected_tool=None,
                error_info=(
                    f"Preferred tool '{normalized_request.preferred_tool}' is not available in "
                    "web_search family."
                ),
            )

        tool = self._tool_registry[selected_tool]
        tool_result = await tool.run(
            TavilyWebSearchToolRequest(
                query_text=normalized_request.query_text,
                target_problem=normalized_request.target_problem,
                freshness_requirement=normalized_request.freshness_requirement,
                include_domains=normalized_request.include_domains,
                exclude_domains=normalized_request.exclude_domains,
                max_search_results=normalized_request.max_search_results,
                max_content_fetches=normalized_request.max_content_fetches,
                min_score_threshold=normalized_request.min_score_threshold,
            )
        )
        return self._wrap_tool_result(
            normalized_request=normalized_request,
            candidate_tools=candidate_tools,
            selected_tool=selected_tool,
            tool_result=tool_result,
        )

    def _normalize_request(self, request: WebSearchFamilyRequest) -> WebSearchFamilyRequest:
        return WebSearchFamilyRequest(
            query_text=request.query_text.strip(),
            target_problem=(request.target_problem or "").strip() or None,
            freshness_requirement=(request.freshness_requirement or "").strip() or None,
            include_domains=[value.strip() for value in request.include_domains if value.strip()],
            exclude_domains=[value.strip() for value in request.exclude_domains if value.strip()],
            max_search_results=request.max_search_results,
            max_content_fetches=request.max_content_fetches,
            min_score_threshold=request.min_score_threshold,
            preferred_tool=(request.preferred_tool or "").strip() or None,
        )

    def _select_tool(
        self,
        request: WebSearchFamilyRequest,
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
        normalized_request: WebSearchFamilyRequest,
        candidate_tools: list[str],
        selected_tool: str,
        tool_result: TavilyWebSearchToolResult,
    ) -> WebSearchFamilyResult:
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

        return WebSearchFamilyResult(
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
        normalized_request: WebSearchFamilyRequest,
        candidate_tools: list[str],
        selected_tool: str | None,
        error_info: str,
    ) -> WebSearchFamilyResult:
        return WebSearchFamilyResult(
            normalized_items=[],
            acquisition_status="failed",
            dropped_item_count=0,
            source_summary={
                "selected_family": self._FAMILY_NAME,
                "selected_tool": selected_tool,
                "normalized_count": 0,
            },
            execution_summary={
                "candidate_tool_count": len(candidate_tools),
                "preferred_tool_requested": normalized_request.preferred_tool,
                "normalized_count": 0,
            },
            retrieval_trace={
                "selected_family": self._FAMILY_NAME,
                "candidate_tools": candidate_tools,
                "selected_tool": selected_tool,
                "preferred_tool": normalized_request.preferred_tool,
                "query_text": normalized_request.query_text,
                "target_problem": normalized_request.target_problem,
                "freshness_requirement": normalized_request.freshness_requirement,
                "include_domains": normalized_request.include_domains,
                "exclude_domains": normalized_request.exclude_domains,
                "family_error": error_info,
            },
            error_info=error_info,
            selected_family=self._FAMILY_NAME,
            candidate_tools=candidate_tools,
            selected_tool=selected_tool,
        )
