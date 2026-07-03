"""Tests for shared typed retrieval output models."""

import pytest
from pydantic import ValidationError

from app.domain.models import (
    NormalizedRetrievalItem,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    SourceReference,
    RetrievalTrace,
)


def test_normalized_retrieval_item_supports_core_fields_and_metadata() -> None:
    item = NormalizedRetrievalItem(
        item_id="item-1",
        source_family="docs_search",
        source_references=[
            SourceReference(
                source_type="document",
                source_url="https://example.test/docs",
            )
        ],
        content="Use typed retrieval items.",
        content_type="text_snippet",
        metadata={"title": "Docs"},
    )

    dumped = item.model_dump()
    assert item.source_references[0].source_url == "https://example.test/docs"
    assert "source_references" in dumped
    assert "source_reference" not in dumped
    assert "source_ref" not in dumped
    assert "source_type" not in dumped
    assert item.metadata["title"] == "Docs"


def test_normalized_retrieval_item_rejects_legacy_source_fields() -> None:
    with pytest.raises(ValidationError):
        NormalizedRetrievalItem(
            item_id="item-1",
            source_family="docs_search",
            source_type="document",
            source_ref="https://example.test/docs",
            content="Use typed retrieval items.",
        )

    with pytest.raises(ValidationError):
        NormalizedRetrievalItem(
            item_id="item-1",
            source_family="docs_search",
            source_reference=SourceReference(
                source_type="document",
                source_url="https://example.test/docs",
            ),
            content="Use typed retrieval items.",
        )


def test_normalized_retrieval_item_requires_source_references() -> None:
    with pytest.raises(ValidationError):
        NormalizedRetrievalItem(
            item_id="item-1",
            source_family="docs_search",
            source_references=[],
            content="Use typed retrieval items.",
        )


def test_source_summary_collects_legacy_extra_fields_into_metadata() -> None:
    summary = RetrievalSourceSummary.model_validate(
        {
            "selected_family": "docs_search",
            "selected_tool": "llms_txt_docs_search_v1",
            "normalized_count": 2,
            "searched_sources": ["openai_api"],
        }
    )

    assert summary.selected_family == "docs_search"
    assert summary.selected_tool == "llms_txt_docs_search_v1"
    assert summary.normalized_count == 2
    assert summary.metadata["searched_sources"] == ["openai_api"]


def test_execution_summary_splits_metrics_and_observability() -> None:
    summary = RetrievalExecutionSummary.model_validate(
        {
            "policy": "policy_v1",
            "normalized_count": 2,
            "search_result_count": 3,
            "query_generation_status": "succeeded",
            "fallback_applied": True,
        }
    )

    assert summary.policy == "policy_v1"
    assert summary.normalized_count == 2
    assert summary.fallback_applied is True
    assert summary.metrics["search_result_count"] == 3
    assert summary.observability["query_generation_status"] == "succeeded"


def test_retrieval_trace_splits_context_errors_and_observability() -> None:
    trace = RetrievalTrace.model_validate(
        {
            "target_problem": "Find docs",
            "selected_family": "docs_search",
            "selected_tool": "llms_txt_docs_search_v1",
            "generated_query": "typed retrieval docs",
            "query_text": "typed retrieval docs",
            "returned_refs": ["doc-1"],
            "search_error": "temporary failure",
            "attempted_urls": ["https://example.test"],
            "attempts": [
                {
                    "selected_family": "docs_search",
                    "generated_query": "typed retrieval docs",
                    "acquisition_status": "success",
                }
            ],
        }
    )

    assert trace.target_problem == "Find docs"
    assert trace.selected_tool == "llms_txt_docs_search_v1"
    assert trace.context["query_text"] == "typed retrieval docs"
    assert trace.errors["search_error"] == "temporary failure"
    assert trace.observability["attempted_urls"] == ["https://example.test"]
    assert trace.attempts[0].acquisition_status == "success"
