"""Runtime-facing tool that combines web search and content fetch."""

from __future__ import annotations

from typing import Any

from app.adapters.web_content_fetch.contracts.web_content_fetch_client_protocol import (
    WebContentFetchClientProtocol,
)
from app.adapters.web_search.contracts.web_search_client_protocol import (
    WebSearchClientProtocol,
)
from app.domain.enums import AcquisitionStatus
from app.domain.models import (
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
    SourceReference,
    TavilyWebSearchToolRequest,
    TavilyWebSearchToolResult,
    WebContentFetchFailedResult,
    WebContentFetchRequest,
    WebContentFetchResponse,
    WebContentFetchResult,
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
            return self._failed_result(str(exc))

        candidates = search_response.results[: normalized_request.max_search_results]
        if not candidates:
            return self._no_result()

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

        return self._create_result(
            normalized_items=normalized_items,
            acquisition_status=acquisition_status,
            execution_summary=execution_summary,
            retrieval_trace=retrieval_trace,
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

    def _failed_result(self, error_info: str) -> TavilyWebSearchToolResult:
        return TavilyWebSearchToolResult(
            normalized_items=[],
            acquisition_status=AcquisitionStatus.FAILED,
            dropped_item_count=0,
            source_summary=RetrievalSourceSummary(
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
                errors={"search_error": error_info},
                observability={
                    "attempted_urls": [],
                    "fetched_urls": [],
                },
            ),
            error_info=error_info,
        )

    def _no_result(self) -> TavilyWebSearchToolResult:
        return TavilyWebSearchToolResult(
            normalized_items=[],
            acquisition_status=AcquisitionStatus.NO_RESULT,
            dropped_item_count=0,
            source_summary=RetrievalSourceSummary(
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

    def _create_result(
        self,
        *,
        normalized_items: list[NormalizedRetrievalItem],
        acquisition_status: AcquisitionStatus,
        execution_summary: RetrievalExecutionSummary,
        retrieval_trace: RetrievalTrace,
    ) -> TavilyWebSearchToolResult:
        return TavilyWebSearchToolResult(
            normalized_items=normalized_items,
            acquisition_status=acquisition_status,
            dropped_item_count=0,
            source_summary=RetrievalSourceSummary(
                normalized_count=len(normalized_items),
            ),
            execution_summary=execution_summary,
            retrieval_trace=retrieval_trace,
            error_info=None,
        )

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
            item, failed_fetch = self._create_normalized_item(
                candidate=candidate,
                rank=rank,
                selected_urls=selected_urls,
                fetch_results_by_url=fetch_results_by_url,
                fetch_failures_by_url=fetch_failures_by_url,
                fetch_error=fetch_error,
            )
            normalized_items.append(item)

            content_fetch_status = item.metadata.get("content_fetch_status")
            if content_fetch_status == "succeeded":
                fetch_success_count += 1
                fetched_urls.append(candidate.url)
            elif content_fetch_status == "empty_content":
                fetch_empty_count += 1
                fetched_urls.append(candidate.url)
            elif content_fetch_status == "failed":
                fetch_failed_count += 1
                if failed_fetch is not None:
                    failed_fetches.append(failed_fetch)

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

    def _create_normalized_item(
        self,
        *,
        candidate: WebSearchResult,
        rank: int,
        selected_urls: set[str],
        fetch_results_by_url: dict[str, WebContentFetchResult],
        fetch_failures_by_url: dict[str, WebContentFetchFailedResult],
        fetch_error: str | None,
    ) -> tuple[NormalizedRetrievalItem, dict[str, str] | None]:
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
        failed_fetch: dict[str, str] | None = None

        # 当前候选网页被选中做正文抓取，需要根据抓取结果决定使用正文还是回退搜索摘要。
        if candidate.url in selected_urls:
            fetched = fetch_results_by_url.get(candidate.url)
            failed = fetch_failures_by_url.get(candidate.url)
            # Provider 返回了有效正文，使用抓取正文作为更完整的 document chunk。
            if (
                fetched is not None
                and fetched.fetch_status == "succeeded"
                and fetched.extracted_content
            ):
                content = fetched.extracted_content
                content_type = "document_chunk"
                metadata["content_fetch_status"] = "succeeded"
                metadata["content_fetch_source"] = fetched.source
                metadata["fetched_images"] = fetched.images
                metadata["fetched_favicon"] = fetched.favicon
                metadata.update(fetched.metadata)
            # Provider 返回了该 URL 的结果，但正文为空，保留搜索摘要并记录降级原因。
            elif fetched is not None and fetched.fetch_status == "empty_content":
                metadata["content_fetch_status"] = "empty_content"
                metadata["fallback_to_search_snippet"] = True
                metadata["content_fetch_source"] = fetched.source
                metadata.update(fetched.metadata)
                if fetched.error_info:
                    metadata["content_fetch_error_info"] = fetched.error_info
            # Provider 明确返回该 URL 的失败结果，回退搜索摘要并保留失败 trace 信息。
            elif failed is not None:
                metadata["content_fetch_status"] = "failed"
                metadata["fallback_to_search_snippet"] = True
                metadata["content_fetch_error_info"] = failed.error_info
                metadata.update(failed.metadata)
                failed_fetch = {"url": failed.url, "error_info": failed.error_info}
            # 整批 content fetch 调用异常，当前被选中的 URL 只能回退到搜索摘要。
            elif fetch_error is not None:
                metadata["content_fetch_status"] = "failed"
                metadata["fallback_to_search_snippet"] = True
                metadata["content_fetch_error_info"] = fetch_error
                failed_fetch = {"url": candidate.url, "error_info": fetch_error}
            # 该 URL 被选中抓取，但 response 中没有匹配结果，按抓取失败降级处理。
            else:
                error_info = "Content fetch did not return a matching result."
                metadata["content_fetch_status"] = "failed"
                metadata["fallback_to_search_snippet"] = True
                metadata["content_fetch_error_info"] = error_info
                failed_fetch = {"url": candidate.url, "error_info": error_info}
        # 当前候选网页未被选中做正文抓取，只使用 web search snippet，不参与 fetch 计数。
        else:
            metadata["content_fetch_status"] = "not_requested"

        item = NormalizedRetrievalItem(
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
        return item, failed_fetch

    def _acquisition_status(
        self,
        *,
        selected_candidates: list[WebSearchResult],
        execution_summary: RetrievalExecutionSummary,
    ) -> AcquisitionStatus:
        if execution_summary["search_result_count"] == 0:
            return AcquisitionStatus.NO_RESULT
        if not selected_candidates:
            return AcquisitionStatus.PARTIAL_SUCCESS
        if execution_summary["fetch_failed_count"] > 0 or execution_summary["fetch_empty_count"] > 0:
            return AcquisitionStatus.PARTIAL_SUCCESS
        if execution_summary["fetch_success_count"] > 0:
            return AcquisitionStatus.SUCCESS
        return AcquisitionStatus.PARTIAL_SUCCESS
