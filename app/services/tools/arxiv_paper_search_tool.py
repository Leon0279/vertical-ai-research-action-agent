"""Runtime-facing tool that combines paper search and paper content fetch."""

from __future__ import annotations

from typing import Any

from app.adapters.paper_content_fetch.contracts.paper_content_fetch_client_protocol import (
    PaperContentFetchClientProtocol,
)
from app.adapters.paper_search.contracts.paper_search_client_protocol import (
    PaperSearchClientProtocol,
)
from app.domain.models import (
    ArxivPaperSearchToolRequest,
    ArxivPaperSearchToolResult,
    PaperContentFetchRequest,
    PaperContentFetchResult,
    PaperSearchQuery,
    PaperSearchResult,
)
from app.domain.models.retrieval import NormalizedRetrievalItem
from app.services.tools.contracts.arxiv_paper_search_tool_protocol import (
    ArxivPaperSearchToolProtocol,
)


class ArxivPaperSearchTool(ArxivPaperSearchToolProtocol):
    """Tool service that searches arXiv papers and fetches full text for top candidates."""

    def __init__(
        self,
        paper_search_client: PaperSearchClientProtocol,
        paper_content_fetch_client: PaperContentFetchClientProtocol,
    ) -> None:
        self._paper_search_client = paper_search_client
        self._paper_content_fetch_client = paper_content_fetch_client

    async def run(self, request: ArxivPaperSearchToolRequest) -> ArxivPaperSearchToolResult:
        """Execute the paper search tool and return normalized candidate materials."""

        normalized_request = self._normalize_request(request)
        try:
            search_response = await self._paper_search_client.search_papers(
                PaperSearchQuery(
                    query_text=normalized_request.query_text,
                    limit=normalized_request.max_search_results,
                    start=0,
                )
            )
        except Exception as exc:
            return self._failed_result(str(exc))

        candidates = search_response.results[: normalized_request.max_search_results]
        if not candidates:
            return self._no_result()

        selected_candidates = self._select_fetch_candidates(candidates, normalized_request)
        fetch_results, fetch_failures = await self._fetch_selected_candidates(selected_candidates)
        normalized_items, execution_summary, retrieval_trace = self._assemble_items(
            candidates=candidates,
            selected_candidates=selected_candidates,
            fetch_results=fetch_results,
            fetch_failures=fetch_failures,
        )
        acquisition_status = self._acquisition_status(
            selected_candidates=selected_candidates,
            execution_summary=execution_summary,
        )

        return ArxivPaperSearchToolResult(
            normalized_items=normalized_items,
            acquisition_status=acquisition_status,
            dropped_item_count=0,
            source_summary={
                "selected_family": "paper_search",
                "selected_tool": "arxiv_paper_search_v1",
                "normalized_count": len(normalized_items),
            },
            execution_summary=execution_summary,
            retrieval_trace=retrieval_trace,
            error_info=None,
        )

    def _normalize_request(
        self,
        request: ArxivPaperSearchToolRequest,
    ) -> ArxivPaperSearchToolRequest:
        return ArxivPaperSearchToolRequest(
            query_text=request.query_text.strip(),
            max_search_results=request.max_search_results,
            max_content_fetches=request.max_content_fetches,
        )

    def _select_fetch_candidates(
        self,
        candidates: list[PaperSearchResult],
        request: ArxivPaperSearchToolRequest,
    ) -> list[PaperSearchResult]:
        if request.max_content_fetches <= 0:
            return []

        eligible_candidates = [
            candidate
            for candidate in candidates
            if (candidate.arxiv_id and candidate.arxiv_id.strip())
            or (candidate.pdf_url and candidate.pdf_url.strip())
        ]
        return eligible_candidates[: request.max_content_fetches]

    async def _fetch_selected_candidates(
        self,
        selected_candidates: list[PaperSearchResult],
    ) -> tuple[dict[str, PaperContentFetchResult], dict[str, dict[str, Any]]]:
        fetch_results: dict[str, PaperContentFetchResult] = {}
        fetch_failures: dict[str, dict[str, Any]] = {}

        for candidate in selected_candidates:
            source_ref = self._source_ref(candidate)
            try:
                request = PaperContentFetchRequest(
                    paper_id=candidate.paper_id,
                    arxiv_id=candidate.arxiv_id,
                    pdf_url=candidate.pdf_url,
                )
                response = await self._paper_content_fetch_client.fetch_content(request)
            except Exception as exc:
                fetch_failures[source_ref] = {
                    "status": "exception",
                    "error_info": str(exc),
                }
                continue
            fetch_results[source_ref] = response
        return fetch_results, fetch_failures

    def _assemble_items(
        self,
        *,
        candidates: list[PaperSearchResult],
        selected_candidates: list[PaperSearchResult],
        fetch_results: dict[str, PaperContentFetchResult],
        fetch_failures: dict[str, dict[str, Any]],
    ) -> tuple[list[NormalizedRetrievalItem], dict[str, int], dict[str, Any]]:
        selected_refs = {self._source_ref(candidate) for candidate in selected_candidates}

        normalized_items: list[NormalizedRetrievalItem] = []
        fetch_success_count = 0
        fetch_empty_count = 0
        fetch_failed_count = 0
        failed_fetches: list[dict[str, Any]] = []
        fetched_papers: list[str] = []

        for rank, candidate in enumerate(candidates, start=1):
            source_ref = self._source_ref(candidate)
            metadata: dict[str, Any] = {
                "title": candidate.title,
                "authors": candidate.authors,
                "paper_id": candidate.paper_id,
                "arxiv_id": candidate.arxiv_id,
                "primary_category": candidate.primary_category,
                "categories": candidate.categories,
                "paper_url": candidate.url,
                "pdf_url": candidate.pdf_url,
                "doi_url": candidate.doi_url,
                "published_at": (
                    candidate.published_at.isoformat() if candidate.published_at else None
                ),
                "updated_at": (
                    candidate.updated_at.isoformat() if candidate.updated_at else None
                ),
                "rank": rank,
                "paper_source_name": candidate.source,
                "paper_summary": candidate.summary,
            }

            content = candidate.summary or ""
            content_type = "text_snippet"
            if source_ref in selected_refs:
                fetched = fetch_results.get(source_ref)
                failed = fetch_failures.get(source_ref)
                if (
                    fetched is not None
                    and fetched.extraction_status == "succeeded"
                    and fetched.extracted_text
                ):
                    content = fetched.extracted_text
                    content_type = "document_chunk"
                    metadata["content_fetch_status"] = "succeeded"
                    metadata["content_fetch_source"] = fetched.source
                    metadata.update(fetched.metadata)
                    fetch_success_count += 1
                    fetched_papers.append(source_ref)
                elif fetched is not None and fetched.extraction_status == "empty_text":
                    metadata["content_fetch_status"] = "empty_text"
                    metadata["fallback_to_paper_summary"] = True
                    metadata["content_fetch_error_info"] = fetched.error_info
                    metadata.update(fetched.metadata)
                    fetch_empty_count += 1
                    failed_fetches.append(
                        {
                            "source_ref": source_ref,
                            "status": "empty_text",
                            "error_info": fetched.error_info,
                        }
                    )
                elif fetched is not None:
                    metadata["content_fetch_status"] = fetched.extraction_status
                    metadata["fallback_to_paper_summary"] = True
                    metadata["content_fetch_error_info"] = fetched.error_info
                    metadata.update(fetched.metadata)
                    fetch_failed_count += 1
                    failed_fetches.append(
                        {
                            "source_ref": source_ref,
                            "status": fetched.extraction_status,
                            "error_info": fetched.error_info,
                        }
                    )
                elif failed is not None:
                    metadata["content_fetch_status"] = failed["status"]
                    metadata["fallback_to_paper_summary"] = True
                    metadata["content_fetch_error_info"] = failed["error_info"]
                    fetch_failed_count += 1
                    failed_fetches.append(
                        {
                            "source_ref": source_ref,
                            "status": failed["status"],
                            "error_info": failed["error_info"],
                        }
                    )
                else:
                    metadata["content_fetch_status"] = "not_returned"
                    metadata["fallback_to_paper_summary"] = True
                    fetch_failed_count += 1
                    failed_fetches.append(
                        {
                            "source_ref": source_ref,
                            "status": "not_returned",
                            "error_info": "Selected paper was not returned by paper_content_fetch.",
                        }
                    )
            else:
                metadata["content_fetch_status"] = "not_requested"

            normalized_items.append(
                NormalizedRetrievalItem(
                    item_id=candidate.paper_id,
                    source_family="paper_search",
                    source_type="paper",
                    source_ref=source_ref,
                    content=content,
                    content_type=content_type,
                    metadata=metadata,
                )
            )

        execution_summary = {
            "search_result_count": len(candidates),
            "selected_for_fetch_count": len(selected_candidates),
            "fetch_success_count": fetch_success_count,
            "fetch_empty_count": fetch_empty_count,
            "fetch_failed_count": fetch_failed_count,
        }
        retrieval_trace = {
            "attempted_papers": [self._source_ref(candidate) for candidate in candidates],
            "selected_for_fetch": [self._source_ref(candidate) for candidate in selected_candidates],
            "fetched_papers": fetched_papers,
            "failed_fetches": failed_fetches,
        }
        return normalized_items, execution_summary, retrieval_trace

    def _acquisition_status(
        self,
        *,
        selected_candidates: list[PaperSearchResult],
        execution_summary: dict[str, int],
    ) -> str:
        if execution_summary["search_result_count"] == 0:
            return "no_result"
        if not selected_candidates:
            return "partial_success"
        if (
            execution_summary["fetch_failed_count"] > 0
            or execution_summary["fetch_empty_count"] > 0
        ):
            return "partial_success"
        if execution_summary["fetch_success_count"] == 0:
            return "partial_success"
        return "success"

    def _source_ref(self, candidate: PaperSearchResult) -> str:
        return candidate.arxiv_id or candidate.url or candidate.paper_id

    def _failed_result(self, error_info: str) -> ArxivPaperSearchToolResult:
        return ArxivPaperSearchToolResult(
            normalized_items=[],
            acquisition_status="failed",
            dropped_item_count=0,
            source_summary={
                "selected_family": "paper_search",
                "selected_tool": "arxiv_paper_search_v1",
                "normalized_count": 0,
            },
            execution_summary={
                "search_result_count": 0,
                "selected_for_fetch_count": 0,
                "fetch_success_count": 0,
                "fetch_empty_count": 0,
                "fetch_failed_count": 1,
            },
            retrieval_trace={
                "search_error": error_info,
                "attempted_papers": [],
                "fetched_papers": [],
            },
            error_info=error_info,
        )

    def _no_result(self) -> ArxivPaperSearchToolResult:
        return ArxivPaperSearchToolResult(
            normalized_items=[],
            acquisition_status="no_result",
            dropped_item_count=0,
            source_summary={
                "selected_family": "paper_search",
                "selected_tool": "arxiv_paper_search_v1",
                "normalized_count": 0,
            },
            execution_summary={
                "search_result_count": 0,
                "selected_for_fetch_count": 0,
                "fetch_success_count": 0,
                "fetch_empty_count": 0,
                "fetch_failed_count": 0,
            },
            retrieval_trace={
                "attempted_papers": [],
                "selected_for_fetch": [],
                "fetched_papers": [],
                "failed_fetches": [],
            },
            error_info=None,
        )
