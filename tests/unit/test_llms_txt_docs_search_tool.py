"""llms_txt_docs_search tool tests."""

from __future__ import annotations

from app.domain.enums import AcquisitionStatus
import asyncio

from app.domain.models import (
    DocsSearchResponse,
    DocsSearchResult,
    LlmsTxtDocsSearchToolRequest,
    RetrievalSourceSummary,
    SourceEvidenceSpan,
    SourceReference,
)
from app.services.tools.llms_txt_docs_search_tool import LlmsTxtDocsSearchTool


class FakeDocsSearchClient:
    def __init__(self, response: DocsSearchResponse | Exception) -> None:
        self.response = response
        self.last_query = None

    async def search_docs(self, query):
        self.last_query = query
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


SEARCH_RESPONSE = DocsSearchResponse(
    results=[
        DocsSearchResult(
            item_id="doc-1",
            title="Retrieval Guide",
            content="Use hybrid retrieval as a strong practical baseline.",
            source_reference=SourceReference(
                source_type="document",
                sub_source_type="openai_api",
                source_id="doc-1",
                source_id_type="docs_entry_id",
                source_url="https://developers.openai.com/api/docs/retrieval",
                title="Retrieval Guide",
                evidence_span=SourceEvidenceSpan(section="Guides"),
                citation_text="Retrieval Guide",
            ),
            score=7.5,
            metadata={"manifest_summary": "Recommended retrieval baseline."},
        ),
        DocsSearchResult(
            item_id="doc-2",
            title="Responses API",
            content="Build agent workflows with hosted tools and structured outputs.",
            source_reference=SourceReference(
                source_type="document",
                sub_source_type="openai_api",
                source_id="doc-2",
                source_id_type="docs_entry_id",
                source_url="https://developers.openai.com/api/docs/responses",
                title="Responses API",
                evidence_span=SourceEvidenceSpan(section="Guides"),
                citation_text="Responses API",
            ),
            score=4.0,
            metadata={"manifest_summary": "Build agent workflows with tools."},
        ),
    ],
    dropped_item_count=1,
    source_summary=RetrievalSourceSummary(
        normalized_count=2,
        metadata={"searched_sub_source_types": ["openai_api", "anthropic_api"]},
    ),
)


def test_run_normal_path_maps_docs_results_to_normalized_items() -> None:
    docs_client = FakeDocsSearchClient(SEARCH_RESPONSE)
    tool = LlmsTxtDocsSearchTool(docs_search_client=docs_client)

    result = asyncio.run(
        tool.run(
            LlmsTxtDocsSearchToolRequest(
                query_text="  retrieval baseline  ",
                target_problem=" Need current implementation guidance. ",
                freshness_requirement=" recent ",
                sub_source_types=[" openai_api ", "", "anthropic_api"],
                max_search_results=2,
            )
        )
    )

    assert docs_client.last_query is not None
    assert docs_client.last_query.query_text == "retrieval baseline"
    assert docs_client.last_query.target_problem == "Need current implementation guidance."
    assert docs_client.last_query.freshness_requirement == "recent"
    assert docs_client.last_query.sub_source_types == ["openai_api", "anthropic_api"]
    assert docs_client.last_query.limit == 2

    assert result.acquisition_status == AcquisitionStatus.PARTIAL_SUCCESS
    assert result.dropped_item_count == 1
    assert len(result.normalized_items) == 2
    assert result.source_summary["normalized_count"] == 2
    assert result.source_summary["searched_sub_source_types"] == ["openai_api", "anthropic_api"]
    assert result.execution_summary.metrics["search_result_count"] == 2
    assert result.execution_summary.normalized_count == 2
    assert result.execution_summary.dropped_item_count == 1
    assert result.retrieval_trace["query_text"] == "retrieval baseline"
    assert result.retrieval_trace["target_problem"] == "Need current implementation guidance."
    assert result.retrieval_trace["selected_sub_source_types"] == [
        "openai_api",
        "anthropic_api",
    ]
    assert result.retrieval_trace["returned_refs"] == [
        "https://developers.openai.com/api/docs/retrieval",
        "https://developers.openai.com/api/docs/responses",
    ]

    first = result.normalized_items[0]
    assert first["item_id"] == "doc-1"
    assert first["source_family"] == "docs_search"
    assert len(first["source_references"]) == 1
    assert first["source_references"][0].source_type == "document"
    assert first["source_references"][0].sub_source_type == "openai_api"
    assert first["source_references"][0].source_id == "doc-1"
    assert first["source_references"][0].source_id_type == "docs_entry_id"
    assert first["source_references"][0].source_url == (
        "https://developers.openai.com/api/docs/retrieval"
    )
    assert first["source_references"][0].evidence_span is not None
    assert first["source_references"][0].evidence_span.section == "Guides"
    assert "source_type" not in first.model_dump()
    assert "source_ref" not in first.model_dump()
    assert "source_reference" not in first.model_dump()
    assert first["content"] == "Use hybrid retrieval as a strong practical baseline."
    assert first["content_type"] == "text_snippet"
    assert first["metadata"]["title"] == "Retrieval Guide"
    assert first["metadata"]["sub_source_type"] == "openai_api"
    assert first["metadata"]["url"] == "https://developers.openai.com/api/docs/retrieval"
    assert first["metadata"]["section"] == "Guides"
    assert "source_reference" not in first["metadata"]
    assert first["metadata"]["rank"] == 1
    assert first["metadata"]["score"] == 7.5
    assert first["metadata"]["manifest_summary"] == "Recommended retrieval baseline."


def test_run_returns_no_result_for_empty_docs_results() -> None:
    tool = LlmsTxtDocsSearchTool(
        docs_search_client=FakeDocsSearchClient(
            DocsSearchResponse(
                results=[],
                dropped_item_count=0,
                source_summary=RetrievalSourceSummary(
                    metadata={"searched_sub_source_types": ["openai_api"]}
                ),
            )
        )
    )

    result = asyncio.run(tool.run(LlmsTxtDocsSearchToolRequest(query_text="missing topic")))

    assert result.acquisition_status == AcquisitionStatus.NO_RESULT
    assert result.normalized_items == []
    assert result.error_info is None
    assert result.execution_summary["normalized_count"] == 0
    assert result.retrieval_trace["returned_refs"] == []


def test_run_returns_failed_when_adapter_raises() -> None:
    tool = LlmsTxtDocsSearchTool(
        docs_search_client=FakeDocsSearchClient(RuntimeError("docs boom"))
    )

    result = asyncio.run(
        tool.run(
            LlmsTxtDocsSearchToolRequest(
                query_text="docs topic",
                sub_source_types=["openai_api"],
            )
        )
    )

    assert result.acquisition_status == AcquisitionStatus.FAILED
    assert result.error_info == "docs boom"
    assert result.normalized_items == []
    assert result.source_summary["normalized_count"] == 0
    assert result.retrieval_trace["selected_sub_source_types"] == ["openai_api"]
    assert result.retrieval_trace["search_error"] == "docs boom"


def test_run_marks_success_when_no_items_are_dropped() -> None:
    tool = LlmsTxtDocsSearchTool(
        docs_search_client=FakeDocsSearchClient(
            DocsSearchResponse(
                results=[SEARCH_RESPONSE.results[0]],
                dropped_item_count=0,
                source_summary=RetrievalSourceSummary(
                    normalized_count=1,
                    metadata={"searched_sub_source_types": ["openai_api"]}
                ),
            )
        )
    )

    result = asyncio.run(tool.run(LlmsTxtDocsSearchToolRequest(query_text="retrieval guide")))

    assert result.acquisition_status == AcquisitionStatus.SUCCESS
    assert result.dropped_item_count == 0
