"""Runtime-facing tool that wraps llms.txt docs search."""

from __future__ import annotations

from app.adapters.docs_search.contracts.docs_search_client_protocol import (
    DocsSearchClientProtocol,
)
from app.domain.models import (
    DocsSearchQuery,
    DocsSearchResponse,
    DocsSearchResult,
    LlmsTxtDocsSearchToolRequest,
    LlmsTxtDocsSearchToolResult,
)
from app.domain.models.retrieval import NormalizedRetrievalItem
from app.services.tools.contracts.llms_txt_docs_search_tool_protocol import (
    LlmsTxtDocsSearchToolProtocol,
)


class LlmsTxtDocsSearchTool(LlmsTxtDocsSearchToolProtocol):
    """Tool service that searches official docs via the llms.txt adapter."""

    def __init__(self, docs_search_client: DocsSearchClientProtocol) -> None:
        self._docs_search_client = docs_search_client

    async def run(
        self,
        request: LlmsTxtDocsSearchToolRequest,
    ) -> LlmsTxtDocsSearchToolResult:
        """Execute docs search and return normalized candidate materials."""

        normalized_request = self._normalize_request(request)
        try:
            search_response = await self._docs_search_client.search_docs(
                DocsSearchQuery(
                    query_text=normalized_request.query_text,
                    target_problem=normalized_request.target_problem,
                    limit=normalized_request.max_search_results,
                    freshness_requirement=normalized_request.freshness_requirement,
                    sub_source_types=normalized_request.sub_source_types,
                )
            )
        except Exception as exc:
            return self._failed_result(
                normalized_request=normalized_request,
                error_info=str(exc),
            )

        normalized_items = self._normalize_items(search_response.results)
        if not normalized_items:
            return self._no_result(
                normalized_request=normalized_request,
                search_response=search_response,
            )

        return LlmsTxtDocsSearchToolResult(
            normalized_items=normalized_items,
            acquisition_status="partial_success"
            if search_response.dropped_item_count > 0
            else "success",
            dropped_item_count=search_response.dropped_item_count,
            source_summary=self._source_summary(
                normalized_count=len(normalized_items),
                search_response=search_response,
            ),
            execution_summary={
                "search_result_count": len(search_response.results),
                "normalized_count": len(normalized_items),
                "dropped_item_count": search_response.dropped_item_count,
            },
            retrieval_trace=self._retrieval_trace(
                normalized_request=normalized_request,
                search_response=search_response,
            ),
            error_info=None,
        )

    def _normalize_request(
        self,
        request: LlmsTxtDocsSearchToolRequest,
    ) -> LlmsTxtDocsSearchToolRequest:
        return LlmsTxtDocsSearchToolRequest(
            query_text=request.query_text.strip(),
            target_problem=(request.target_problem or "").strip() or None,
            freshness_requirement=(request.freshness_requirement or "").strip() or None,
            sub_source_types=[
                value.strip() for value in request.sub_source_types if value.strip()
            ],
            max_search_results=request.max_search_results,
        )

    def _normalize_items(self, results: list[DocsSearchResult]) -> list[NormalizedRetrievalItem]:
        normalized_items: list[NormalizedRetrievalItem] = []
        for rank, result in enumerate(results, start=1):
            source_reference = result.source_reference
            evidence_span = source_reference.evidence_span
            metadata = {
                "title": result.title,
                "sub_source_type": source_reference.sub_source_type,
                "url": source_reference.source_url,
                "section": evidence_span.section if evidence_span else None,
                "source_reference": source_reference.model_dump(mode="json"),
                "rank": rank,
                "score": result.score,
            }
            metadata.update(result.metadata)
            normalized_items.append(
                NormalizedRetrievalItem(
                    item_id=result.item_id,
                    source_family="docs_search",
                    source_type="document",
                    source_ref=self._source_ref(result),
                    content=result.content,
                    content_type="text_snippet",
                    metadata=metadata,
                )
            )
        return normalized_items

    def _source_ref(self, result: DocsSearchResult) -> str:
        return (
            result.source_reference.source_url
            or result.source_reference.source_id
            or result.item_id
        )

    def _source_summary(
        self,
        *,
        normalized_count: int,
        search_response: DocsSearchResponse,
    ) -> dict[str, object]:
        source_summary = {
            "selected_family": "docs_search",
            "selected_tool": "llms_txt_docs_search_v1",
            "normalized_count": normalized_count,
        }
        searched_sub_source_types = search_response.source_summary.get(
            "searched_sub_source_types"
        )
        if isinstance(searched_sub_source_types, list):
            source_summary["searched_sub_source_types"] = searched_sub_source_types
        return source_summary

    def _retrieval_trace(
        self,
        *,
        normalized_request: LlmsTxtDocsSearchToolRequest,
        search_response: DocsSearchResponse,
    ) -> dict[str, object]:
        selected_sub_source_types = search_response.source_summary.get(
            "searched_sub_source_types"
        )
        if not isinstance(selected_sub_source_types, list):
            selected_sub_source_types = normalized_request.sub_source_types
        return {
            "query_text": normalized_request.query_text,
            "target_problem": normalized_request.target_problem,
            "selected_sub_source_types": selected_sub_source_types,
            "returned_refs": [self._source_ref(result) for result in search_response.results],
        }

    def _failed_result(
        self,
        *,
        normalized_request: LlmsTxtDocsSearchToolRequest,
        error_info: str,
    ) -> LlmsTxtDocsSearchToolResult:
        return LlmsTxtDocsSearchToolResult(
            normalized_items=[],
            acquisition_status="failed",
            dropped_item_count=0,
            source_summary={
                "selected_family": "docs_search",
                "selected_tool": "llms_txt_docs_search_v1",
                "normalized_count": 0,
            },
            execution_summary={
                "search_result_count": 0,
                "normalized_count": 0,
                "dropped_item_count": 0,
            },
            retrieval_trace={
                "query_text": normalized_request.query_text,
                "target_problem": normalized_request.target_problem,
                "selected_sub_source_types": normalized_request.sub_source_types,
                "returned_refs": [],
                "search_error": error_info,
            },
            error_info=error_info,
        )

    def _no_result(
        self,
        *,
        normalized_request: LlmsTxtDocsSearchToolRequest,
        search_response: DocsSearchResponse,
    ) -> LlmsTxtDocsSearchToolResult:
        return LlmsTxtDocsSearchToolResult(
            normalized_items=[],
            acquisition_status="no_result",
            dropped_item_count=search_response.dropped_item_count,
            source_summary=self._source_summary(
                normalized_count=0,
                search_response=search_response,
            ),
            execution_summary={
                "search_result_count": len(search_response.results),
                "normalized_count": 0,
                "dropped_item_count": search_response.dropped_item_count,
            },
            retrieval_trace=self._retrieval_trace(
                normalized_request=normalized_request,
                search_response=search_response,
            ),
            error_info=None,
        )
