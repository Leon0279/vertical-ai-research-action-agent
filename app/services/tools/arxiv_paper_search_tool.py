"""Runtime-facing tool that combines paper search and paper content fetch."""

from __future__ import annotations

from typing import Any

from app.adapters.paper_content_fetch.contracts.paper_content_fetch_client_protocol import (
    PaperContentFetchClientProtocol,
)
from app.adapters.paper_search.contracts.paper_search_client_protocol import (
    PaperSearchClientProtocol,
)
from app.common.observability import sanitize_sensitive_text
from app.domain.enums import AcquisitionStatus, FamilyName
from app.domain.models import (
    ArxivPaperSearchToolRequest,
    ArxivPaperSearchToolResult,
    PaperContentFetchRequest,
    PaperContentFetchResult,
    PaperSearchQuery,
    PaperSearchResult,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
    SourceReference,
)
from app.domain.models.retrieval import NormalizedRetrievalItem
from app.services.tools.contracts.arxiv_paper_search_tool_protocol import (
    ArxivPaperSearchToolProtocol,
)


class ArxivPaperSearchTool(ArxivPaperSearchToolProtocol):
    """封装arXiv论文搜索的工具调用逻辑。

Tool service that searches arXiv papers and fetches full text for top candidates."""

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
            return self._failed_result(
                sanitize_sensitive_text(exc, max_length=500),
                diagnostics=self._exception_diagnostics(
                    exc,
                    default_stage="paper_search",
                ),
            )

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
            source_summary=RetrievalSourceSummary(
                selected_family=FamilyName.PAPER_SEARCH,
                normalized_count=len(normalized_items),
            ),
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
            if self._arxiv_id(candidate)
        ]
        return eligible_candidates[: request.max_content_fetches]

    async def _fetch_selected_candidates(
        self,
        selected_candidates: list[PaperSearchResult],
    ) -> tuple[dict[str, PaperContentFetchResult], dict[str, dict[str, Any]]]:
        fetch_results: dict[str, PaperContentFetchResult] = {}
        fetch_failures: dict[str, dict[str, Any]] = {}

        for candidate in selected_candidates:
            paper_id = candidate.paper_id
            try:
                request = PaperContentFetchRequest(
                    paper_id=candidate.paper_id,
                    paper_id_type=candidate.paper_id_type,
                )
                response = await self._paper_content_fetch_client.fetch_content(request)
            except Exception as exc:
                fetch_failures[paper_id] = {
                    "status": "exception",
                    "error_info": sanitize_sensitive_text(exc, max_length=500),
                    **self._exception_diagnostics(
                        exc,
                        default_stage="paper_content_fetch",
                    ),
                }
                continue
            fetch_results[paper_id] = response
        return fetch_results, fetch_failures

    def _assemble_items(
        self,
        *,
        candidates: list[PaperSearchResult],
        selected_candidates: list[PaperSearchResult],
        fetch_results: dict[str, PaperContentFetchResult],
        fetch_failures: dict[str, dict[str, Any]],
    ) -> tuple[list[NormalizedRetrievalItem], RetrievalExecutionSummary, RetrievalTrace]:
        selected_paper_ids = {candidate.paper_id for candidate in selected_candidates}

        normalized_items: list[NormalizedRetrievalItem] = []
        fetch_success_count = 0
        fetch_empty_count = 0
        fetch_failed_count = 0
        failed_fetches: list[dict[str, Any]] = []
        fetched_paper_ids: list[str] = []

        for rank, candidate in enumerate(candidates, start=1):
            paper_id = candidate.paper_id
            metadata: dict[str, Any] = {
                "title": candidate.title,
                "authors": candidate.authors,
                "paper_id": candidate.paper_id,
                "paper_id_type": candidate.paper_id_type,
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
            arxiv_id = self._arxiv_id(candidate)
            if arxiv_id:
                metadata["arxiv_id"] = arxiv_id

            content = candidate.summary or ""
            content_type = "text_snippet"
            if paper_id in selected_paper_ids:
                fetched = fetch_results.get(paper_id)
                failed = fetch_failures.get(paper_id)
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
                    fetched_paper_ids.append(paper_id)
                elif fetched is not None and fetched.extraction_status == "empty_text":
                    metadata["content_fetch_status"] = "empty_text"
                    metadata["fallback_to_paper_summary"] = True
                    metadata["content_fetch_error_info"] = fetched.error_info
                    metadata.update(fetched.metadata)
                    fetch_empty_count += 1
                    failed_fetches.append(
                        {
                            "paper_id": paper_id,
                            "paper_id_type": candidate.paper_id_type,
                            "status": "empty_text",
                            "error_info": fetched.error_info,
                            **self._content_fetch_diagnostics(fetched.metadata),
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
                            "paper_id": paper_id,
                            "paper_id_type": candidate.paper_id_type,
                            "status": fetched.extraction_status,
                            "error_info": fetched.error_info,
                            **self._content_fetch_diagnostics(fetched.metadata),
                        }
                    )
                elif failed is not None:
                    metadata["content_fetch_status"] = failed["status"]
                    metadata["fallback_to_paper_summary"] = True
                    metadata["content_fetch_error_info"] = failed["error_info"]
                    fetch_failed_count += 1
                    failed_fetches.append(
                        {
                            "paper_id": paper_id,
                            "paper_id_type": candidate.paper_id_type,
                            "status": failed["status"],
                            "error_info": failed["error_info"],
                            **{
                                key: value
                                for key, value in failed.items()
                                if key not in {"status", "error_info"}
                            },
                        }
                    )
                else:
                    metadata["content_fetch_status"] = "not_returned"
                    metadata["fallback_to_paper_summary"] = True
                    fetch_failed_count += 1
                    failed_fetches.append(
                        {
                            "paper_id": paper_id,
                            "paper_id_type": candidate.paper_id_type,
                            "status": "not_returned",
                            "error_info": "Selected paper was not returned by paper_content_fetch.",
                        }
                    )
            else:
                metadata["content_fetch_status"] = "not_requested"

            normalized_items.append(
                NormalizedRetrievalItem(
                    item_id=candidate.paper_id,
                    source_family=FamilyName.PAPER_SEARCH,
                    source_references=[self._source_reference(candidate)],
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
            selected_family=FamilyName.PAPER_SEARCH,
            observability={
                "attempted_paper_ids": [candidate.paper_id for candidate in candidates],
                "selected_paper_ids": [candidate.paper_id for candidate in selected_candidates],
                "fetched_paper_ids": fetched_paper_ids,
                "failed_fetches": failed_fetches,
                **self._fetch_failure_summary(failed_fetches),
            },
        )
        return normalized_items, execution_summary, retrieval_trace

    def _acquisition_status(
        self,
        *,
        selected_candidates: list[PaperSearchResult],
        execution_summary: RetrievalExecutionSummary,
    ) -> AcquisitionStatus:
        if execution_summary["search_result_count"] == 0:
            return AcquisitionStatus.NO_RESULT
        if not selected_candidates:
            return AcquisitionStatus.PARTIAL_SUCCESS
        if (
            execution_summary["fetch_failed_count"] > 0
            or execution_summary["fetch_empty_count"] > 0
        ):
            return AcquisitionStatus.PARTIAL_SUCCESS
        if execution_summary["fetch_success_count"] == 0:
            return AcquisitionStatus.PARTIAL_SUCCESS
        return AcquisitionStatus.SUCCESS

    def _source_reference(self, candidate: PaperSearchResult) -> SourceReference:
        return SourceReference(
            source_type="paper",
            source_id=candidate.paper_id,
            source_id_type=candidate.paper_id_type,
            source_url=candidate.url,
            title=candidate.title,
            authors=candidate.authors,
            published_at=candidate.published_at,
            citation_text=candidate.title,
            metadata={
                "paper_id": candidate.paper_id,
                "primary_category": candidate.primary_category,
                "categories": candidate.categories,
                "pdf_url": candidate.pdf_url,
                "doi_url": candidate.doi_url,
                "source": candidate.source,
            },
        )

    def _arxiv_id(self, candidate: PaperSearchResult) -> str | None:
        if candidate.paper_id_type != "arxiv_id":
            return None
        return candidate.paper_id.strip() or None

    def _failed_result(
        self,
        error_info: str,
        *,
        diagnostics: dict[str, Any] | None = None,
    ) -> ArxivPaperSearchToolResult:
        safe_diagnostics = diagnostics or {}
        return ArxivPaperSearchToolResult(
            normalized_items=[],
            acquisition_status=AcquisitionStatus.FAILED,
            dropped_item_count=0,
            source_summary=RetrievalSourceSummary(
                selected_family=FamilyName.PAPER_SEARCH,
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
                observability=safe_diagnostics,
            ),
            retrieval_trace=RetrievalTrace(
                selected_family=FamilyName.PAPER_SEARCH,
                errors={"search_error": error_info},
                observability={
                    "attempted_paper_ids": [],
                    "fetched_paper_ids": [],
                    **safe_diagnostics,
                },
            ),
            error_info=error_info,
        )

    def _exception_diagnostics(
        self,
        error: BaseException,
        *,
        default_stage: str,
    ) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "failure_stage": getattr(error, "stage", default_stage),
                "failure_reason": getattr(error, "failure_reason", "unknown_error"),
                "error_category": getattr(error, "error_category", "unknown_error"),
                "provider_http_status": getattr(error, "status_code", None),
                "retryable": getattr(error, "retryable", False),
                "exception_type": (
                    getattr(error, "cause_type", None) or type(error).__name__
                ),
            }.items()
            if value is not None
        }

    def _content_fetch_diagnostics(self, metadata: dict[str, Any]) -> dict[str, Any]:
        allowed_keys = {
            "failure_stage",
            "failure_reason",
            "error_category",
            "provider_http_status",
            "retryable",
            "exception_type",
            "response_content_type",
            "download_bytes",
        }
        return {
            key: metadata[key]
            for key in allowed_keys
            if metadata.get(key) is not None
        }

    def _fetch_failure_summary(
        self,
        failed_fetches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not failed_fetches:
            return {}
        first = failed_fetches[0]
        return {
            key: value
            for key, value in {
                "failure_stage": first.get("failure_stage") or "paper_content_fetch",
                "failure_reason": first.get("failure_reason"),
                "error_category": first.get("error_category"),
                "provider_http_status": first.get("provider_http_status"),
                "retryable": first.get("retryable"),
                "exception_type": first.get("exception_type"),
                "attempt_error_info": first.get("error_info"),
                "content_fetch_failure_count": len(failed_fetches),
            }.items()
            if value is not None
        }

    def _no_result(self) -> ArxivPaperSearchToolResult:
        return ArxivPaperSearchToolResult(
            normalized_items=[],
            acquisition_status=AcquisitionStatus.NO_RESULT,
            dropped_item_count=0,
            source_summary=RetrievalSourceSummary(
                selected_family=FamilyName.PAPER_SEARCH,
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
                selected_family=FamilyName.PAPER_SEARCH,
                observability={
                    "attempted_paper_ids": [],
                    "selected_paper_ids": [],
                    "fetched_paper_ids": [],
                    "failed_fetches": [],
                },
            ),
            error_info=None,
        )
