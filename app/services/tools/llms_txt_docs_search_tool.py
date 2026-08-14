"""Runtime-facing tool that wraps llms.txt docs search."""

from __future__ import annotations

from app.domain.enums import AcquisitionStatus, FamilyName

from app.adapters.docs_search.contracts.docs_search_client_protocol import (
    DocsSearchClientProtocol,
)
from app.domain.models import (
    DocsSearchQuery,
    DocsSearchResponse,
    DocsSearchResult,
    LlmsTxtDocsSearchToolRequest,
    LlmsTxtDocsSearchToolResult,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)
from app.domain.models.retrieval import NormalizedRetrievalItem
from app.services.tools.contracts.llms_txt_docs_search_tool_protocol import (
    LlmsTxtDocsSearchToolProtocol,
)


class LlmsTxtDocsSearchTool(LlmsTxtDocsSearchToolProtocol):
    """封装 llms.txt 文档搜索工具的执行逻辑。

Tool service that searches official docs via the llms.txt adapter."""

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
            return self._create_failed_result(
                normalized_request=normalized_request,
                error_info=str(exc),
            )

        normalized_items = self._normalize_items(search_response.results)
        if not normalized_items:
            return self._create_no_result(
                normalized_request=normalized_request,
                search_response=search_response,
            )

        return self._create_result(
            normalized_request=normalized_request,
            search_response=search_response,
            normalized_items=normalized_items,
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
                "rank": rank,
                "score": result.score,
            }
            metadata.update(result.metadata)
            normalized_items.append(
                NormalizedRetrievalItem(
                    item_id=result.item_id,
                    source_family=FamilyName.DOCS_SEARCH,
                    source_references=[source_reference],
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

    def _create_result(
        self,
        *,
        normalized_request: LlmsTxtDocsSearchToolRequest,
        search_response: DocsSearchResponse,
        normalized_items: list[NormalizedRetrievalItem],
    ) -> LlmsTxtDocsSearchToolResult:
        return LlmsTxtDocsSearchToolResult(
            normalized_items=normalized_items,
            acquisition_status=AcquisitionStatus.PARTIAL_SUCCESS
            if search_response.dropped_item_count > 0
            else AcquisitionStatus.SUCCESS,
            dropped_item_count=search_response.dropped_item_count,
            source_summary=self._source_summary(
                normalized_count=len(normalized_items),
                search_response=search_response,
            ),
            execution_summary=self._execution_summary(
                search_result_count=len(search_response.results),
                normalized_count=len(normalized_items),
                dropped_item_count=search_response.dropped_item_count,
            ),
            retrieval_trace=self._retrieval_trace(
                normalized_request=normalized_request,
                search_response=search_response,
            ),
            error_info=None,
        )

    def _source_summary(
        self,
        *,
        normalized_count: int,
        search_response: DocsSearchResponse,
    ) -> RetrievalSourceSummary:
        return search_response.source_summary.model_copy(
            update={
                "selected_family": FamilyName.DOCS_SEARCH,
                "normalized_count": normalized_count,
            }
        )

    def _execution_summary(
        self,
        *,
        search_result_count: int,
        normalized_count: int,
        dropped_item_count: int,
    ) -> RetrievalExecutionSummary:
        return RetrievalExecutionSummary(
            normalized_count=normalized_count,
            dropped_item_count=dropped_item_count,
            metrics={
                "search_result_count": search_result_count,
            },
        )

    def _retrieval_trace(
        self,
        *,
        normalized_request: LlmsTxtDocsSearchToolRequest,
        search_response: DocsSearchResponse,
    ) -> RetrievalTrace:
        selected_sub_source_types = search_response.source_summary.get(
            "searched_sub_source_types"
        )
        if not isinstance(selected_sub_source_types, list):
            selected_sub_source_types = normalized_request.sub_source_types
        return RetrievalTrace(
            target_problem=normalized_request.target_problem,
            selected_family=FamilyName.DOCS_SEARCH,
            returned_refs=[self._source_ref(result) for result in search_response.results],
            context={
                "query_text": normalized_request.query_text,
                "selected_sub_source_types": selected_sub_source_types,
            },
        )

    def _create_failed_result(
        self,
        *,
        normalized_request: LlmsTxtDocsSearchToolRequest,
        error_info: str,
    ) -> LlmsTxtDocsSearchToolResult:
        return LlmsTxtDocsSearchToolResult(
            normalized_items=[],
            acquisition_status=AcquisitionStatus.FAILED,
            dropped_item_count=0,
            source_summary=RetrievalSourceSummary(
                selected_family=FamilyName.DOCS_SEARCH,
                normalized_count=0,
            ),
            execution_summary=self._execution_summary(
                search_result_count=0,
                normalized_count=0,
                dropped_item_count=0,
            ),
            retrieval_trace=RetrievalTrace(
                target_problem=normalized_request.target_problem,
                selected_family=FamilyName.DOCS_SEARCH,
                returned_refs=[],
                context={
                    "query_text": normalized_request.query_text,
                    "selected_sub_source_types": normalized_request.sub_source_types,
                },
                errors={"search_error": error_info},
            ),
            error_info=error_info,
        )

    def _create_no_result(
        self,
        *,
        normalized_request: LlmsTxtDocsSearchToolRequest,
        search_response: DocsSearchResponse,
    ) -> LlmsTxtDocsSearchToolResult:
        return LlmsTxtDocsSearchToolResult(
            normalized_items=[],
            acquisition_status=AcquisitionStatus.NO_RESULT,
            dropped_item_count=search_response.dropped_item_count,
            source_summary=self._source_summary(
                normalized_count=0,
                search_response=search_response,
            ),
            execution_summary=self._execution_summary(
                search_result_count=len(search_response.results),
                normalized_count=0,
                dropped_item_count=search_response.dropped_item_count,
            ),
            retrieval_trace=self._retrieval_trace(
                normalized_request=normalized_request,
                search_response=search_response,
            ),
            error_info=None,
        )
