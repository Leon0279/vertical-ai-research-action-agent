"""Runtime-facing tool that combines web search and content fetch."""

from __future__ import annotations

from typing import Any

from app.adapters.web_content_fetch.contracts.web_content_fetch_client_protocol import (
    WebContentFetchClientProtocol,
)
from app.adapters.web_search.contracts.web_search_client_protocol import (
    WebSearchClientProtocol,
)
from app.domain.models import (
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
    SourceReference,
    TavilyWebSearchToolRequest,
    TavilyWebSearchToolResult,
    WebContentFetchRequest,
    WebContentFetchResponse,
    WebSearchQuery,
    WebSearchResult,
)
from app.domain.models.retrieval import NormalizedRetrievalItem
from app.services.tools.contracts.tavily_web_search_tool_protocol import (
    TavilyWebSearchToolProtocol,
)


class TavilyWebSearchTool(TavilyWebSearchToolProtocol):
    """Tool service that searches the web and fetches content for top candidates."""

    def __init__(
        self,
        web_search_client: WebSearchClientProtocol,
        web_content_fetch_client: WebContentFetchClientProtocol,
    ) -> None:
        self._web_search_client = web_search_client
        self._web_content_fetch_client = web_content_fetch_client

    async def run(self, request: TavilyWebSearchToolRequest) -> TavilyWebSearchToolResult:
        """Execute the web search tool and return normalized candidate materials."""

        normalized_request = self._normalize_request(request)
        try:
            search_response = await self._web_search_client.search_web(
                WebSearchQuery(
                    query_text=normalized_request.query_text,
                    target_problem=normalized_request.target_problem,
                    limit=normalized_request.max_search_results,
                    freshness_requirement=normalized_request.freshness_requirement,
                    include_domains=normalized_request.include_domains,
                    exclude_domains=normalized_request.exclude_domains,
                )
            )
        except Exception as exc:
            return TavilyWebSearchToolResult(
                normalized_items=[],
                acquisition_status="failed",
                dropped_item_count=0,
                source_summary=RetrievalSourceSummary(
                    selected_family="web_search",
                    selected_tool="tavily_web_search_v1",
                    normalized_count=0,
                ),
                execution_summary=RetrievalExecutionSummary(
                    normalized_count=0,
                    dropped_item_count=0,
                    metrics={
                        "search_result_count": 0,
                        "selected_for_fetch_count": 0,
                        "fetch_success_count": 0,
                        "fetch_empty_count": 0,
                        "fetch_failed_count": 1,
                    },
                ),
                retrieval_trace=RetrievalTrace(
                    errors={"search_error": str(exc)},
                    observability={
                        "attempted_urls": [],
                        "fetched_urls": [],
                    },
                ),
                error_info=str(exc),
            )

        candidates = search_response.results[: normalized_request.max_search_results]
        if not candidates:
            return TavilyWebSearchToolResult(
                normalized_items=[],
                acquisition_status="no_result",
                dropped_item_count=0,
                source_summary=RetrievalSourceSummary(
                    selected_family="web_search",
                    selected_tool="tavily_web_search_v1",
                    normalized_count=0,
                ),
                execution_summary=RetrievalExecutionSummary(
                    normalized_count=0,
                    dropped_item_count=0,
                    metrics={
                        "search_result_count": 0,
                        "selected_for_fetch_count": 0,
                        "fetch_success_count": 0,
                        "fetch_empty_count": 0,
                        "fetch_failed_count": 0,
                    },
                ),
                retrieval_trace=RetrievalTrace(
                    observability={
                        "attempted_urls": [],
                        "fetched_urls": [],
                        "failed_fetches": [],
                    },
                ),
                error_info=None,
            )

        selected_candidates = self._select_fetch_candidates(candidates, normalized_request)
        fetch_response, fetch_error = await self._fetch_selected_candidates(selected_candidates)
        normalized_items, execution_summary, retrieval_trace = self._assemble_items(
            candidates=candidates,
            selected_candidates=selected_candidates,
            fetch_response=fetch_response,
            fetch_error=fetch_error,
        )
        acquisition_status = self._acquisition_status(
            selected_candidates=selected_candidates,
            execution_summary=execution_summary,
        )

        return TavilyWebSearchToolResult(
            normalized_items=normalized_items,
            acquisition_status=acquisition_status,
            dropped_item_count=0,
            source_summary=RetrievalSourceSummary(
                selected_family="web_search",
                selected_tool="tavily_web_search_v1",
                normalized_count=len(normalized_items),
            ),
            execution_summary=execution_summary,
            retrieval_trace=retrieval_trace,
            error_info=None,
        )

    def _normalize_request(
        self,
        request: TavilyWebSearchToolRequest,
    ) -> TavilyWebSearchToolRequest:
        return TavilyWebSearchToolRequest(
            query_text=request.query_text.strip(),
            target_problem=(request.target_problem or "").strip() or None,
            freshness_requirement=(request.freshness_requirement or "").strip() or None,
            include_domains=[value.strip() for value in request.include_domains if value.strip()],
            exclude_domains=[value.strip() for value in request.exclude_domains if value.strip()],
            max_search_results=request.max_search_results,
            max_content_fetches=request.max_content_fetches,
            min_score_threshold=request.min_score_threshold,
        )

    def _select_fetch_candidates(
        self,
        candidates: list[WebSearchResult],
        request: TavilyWebSearchToolRequest,
    ) -> list[WebSearchResult]:
        if request.max_content_fetches <= 0:
            return []

        high_score = [
            candidate
            for candidate in candidates
            if candidate.score >= request.min_score_threshold
        ]
        selected = high_score[: request.max_content_fetches]
        if len(selected) >= request.max_content_fetches:
            return selected

        selected_urls = {candidate.url for candidate in selected}
        for candidate in candidates:
            if candidate.url in selected_urls:
                continue
            selected.append(candidate)
            selected_urls.add(candidate.url)
            if len(selected) >= request.max_content_fetches:
                break
        return selected

    async def _fetch_selected_candidates(
        self,
        selected_candidates: list[WebSearchResult],
    ) -> tuple[WebContentFetchResponse | None, str | None]:
        if not selected_candidates:
            return None, None
        urls = [candidate.url for candidate in selected_candidates]
        try:
            response = await self._web_content_fetch_client.fetch_content(
                WebContentFetchRequest(
                    urls=urls,
                    format="markdown",
                )
            )
        except Exception as exc:
            return None, str(exc)
        return response, None

    def _assemble_items(
        self,
        *,
        candidates: list[WebSearchResult],
        selected_candidates: list[WebSearchResult],
        fetch_response: WebContentFetchResponse | None,
        fetch_error: str | None,
    ) -> tuple[list[NormalizedRetrievalItem], RetrievalExecutionSummary, RetrievalTrace]:
        fetch_results_by_url = {
            result.url: result for result in (fetch_response.results if fetch_response else [])
        }
        fetch_failures_by_url = {
            result.url: result for result in (fetch_response.failed_results if fetch_response else [])
        }
        selected_urls = {candidate.url for candidate in selected_candidates}

        normalized_items: list[NormalizedRetrievalItem] = []
        fetch_success_count = 0
        fetch_empty_count = 0
        fetch_failed_count = 0
        failed_fetches: list[dict[str, Any]] = []
        fetched_urls: list[str] = []

        for rank, candidate in enumerate(candidates, start=1):
            metadata: dict[str, Any] = {
                "title": candidate.title,
                "rank": rank,
                "score": candidate.score,
                "search_snippet": candidate.snippet,
                "search_source_name": candidate.source_name,
                "published_at": (
                    candidate.published_at.isoformat() if candidate.published_at else None
                ),
            }
            metadata.update(candidate.metadata)

            content = candidate.snippet
            content_type = "text_snippet"
            if candidate.url in selected_urls:
                fetched = fetch_results_by_url.get(candidate.url)
                failed = fetch_failures_by_url.get(candidate.url)
                if fetched is not None and fetched.fetch_status == "succeeded" and fetched.extracted_content:
                    content = fetched.extracted_content
                    content_type = "document_chunk"
                    metadata["content_fetch_status"] = "succeeded"
                    metadata["content_fetch_source"] = fetched.source
                    metadata["fetched_images"] = fetched.images
                    metadata["fetched_favicon"] = fetched.favicon
                    metadata.update(fetched.metadata)
                    fetch_success_count += 1
                    fetched_urls.append(candidate.url)
                elif fetched is not None and fetched.fetch_status == "empty_content":
                    metadata["content_fetch_status"] = "empty_content"
                    metadata["fallback_to_search_snippet"] = True
                    metadata["content_fetch_source"] = fetched.source
                    metadata.update(fetched.metadata)
                    if fetched.error_info:
                        metadata["content_fetch_error_info"] = fetched.error_info
                    fetch_empty_count += 1
                    fetched_urls.append(candidate.url)
                elif failed is not None:
                    metadata["content_fetch_status"] = "failed"
                    metadata["fallback_to_search_snippet"] = True
                    metadata["content_fetch_error_info"] = failed.error_info
                    metadata.update(failed.metadata)
                    fetch_failed_count += 1
                    failed_fetches.append(
                        {"url": failed.url, "error_info": failed.error_info}
                    )
                elif fetch_error is not None:
                    metadata["content_fetch_status"] = "failed"
                    metadata["fallback_to_search_snippet"] = True
                    metadata["content_fetch_error_info"] = fetch_error
                    fetch_failed_count += 1
                    failed_fetches.append(
                        {"url": candidate.url, "error_info": fetch_error}
                    )
                else:
                    metadata["content_fetch_status"] = "failed"
                    metadata["fallback_to_search_snippet"] = True
                    metadata["content_fetch_error_info"] = (
                        "Content fetch did not return a matching result."
                    )
                    fetch_failed_count += 1
                    failed_fetches.append(
                        {
                            "url": candidate.url,
                            "error_info": "Content fetch did not return a matching result.",
                        }
                    )
            else:
                metadata["content_fetch_status"] = "not_requested"

            normalized_items.append(
                NormalizedRetrievalItem(
                    item_id=candidate.item_id,
                    source_family="web_search",
                    source_references=[
                        SourceReference(
                            source_type="web_page",
                            source_url=candidate.url,
                            title=candidate.title,
                            published_at=candidate.published_at,
                            citation_text=candidate.title,
                            metadata={"source_name": candidate.source_name},
                        )
                    ],
                    content=content,
                    content_type=content_type,
                    metadata=metadata,
                )
            )

        execution_summary = RetrievalExecutionSummary(
            normalized_count=len(normalized_items),
            dropped_item_count=0,
            metrics={
                "search_result_count": len(candidates),
                "selected_for_fetch_count": len(selected_candidates),
                "fetch_success_count": fetch_success_count,
                "fetch_empty_count": fetch_empty_count,
                "fetch_failed_count": fetch_failed_count,
            },
        )
        retrieval_trace = RetrievalTrace(
            observability={
                "attempted_urls": [candidate.url for candidate in candidates],
                "selected_for_fetch": [candidate.url for candidate in selected_candidates],
                "fetched_urls": fetched_urls,
                "failed_fetches": failed_fetches,
            },
        )
        return normalized_items, execution_summary, retrieval_trace

    def _acquisition_status(
        self,
        *,
        selected_candidates: list[WebSearchResult],
        execution_summary: RetrievalExecutionSummary,
    ) -> str:
        if execution_summary["search_result_count"] == 0:
            return "no_result"
        if not selected_candidates:
            return "partial_success"
        if execution_summary["fetch_failed_count"] > 0 or execution_summary["fetch_empty_count"] > 0:
            return "partial_success"
        if execution_summary["fetch_success_count"] > 0:
            return "success"
        return "partial_success"
