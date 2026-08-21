"""Tests for source provenance models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.models import SourceEvidenceSpan, SourceReference


def test_url_only_source_reference_is_valid() -> None:
    reference = SourceReference(
        source_type="web_page",
        source_url="https://example.test/article",
        title="Example Article",
        publisher="Example Publisher",
        metadata={"rank": 1},
    )

    assert reference.source_type == "web_page"
    assert reference.source_url == "https://example.test/article"
    assert reference.source_id is None
    assert reference.metadata["rank"] == 1


def test_id_only_source_reference_is_valid() -> None:
    reference = SourceReference(
        source_type="paper",
        source_id="2401.00001",
        source_id_type="arxiv_id",
        authors=[" Ada Lovelace ", "", "Grace Hopper"],
    )

    assert reference.source_id == "2401.00001"
    assert reference.source_id_type == "arxiv_id"
    assert reference.authors == ["Ada Lovelace", "Grace Hopper"]


def test_source_reference_deduplication_key_prefers_url_then_id() -> None:
    url_reference = SourceReference(
        source_type="web_page",
        source_url="https://example.test/article",
        source_id="fallback-id",
        source_id_type="example",
    )
    id_reference = SourceReference(
        source_type="paper",
        source_id="2401.00001",
        source_id_type="arxiv_id",
    )

    assert url_reference.deduplication_key() == "url:https://example.test/article"
    assert id_reference.deduplication_key() == "id:arxiv_id:2401.00001"


def test_source_type_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        SourceReference(source_type="  ", source_url="https://example.test")


def test_source_id_or_source_url_is_required() -> None:
    with pytest.raises(ValidationError):
        SourceReference(source_type="paper")


def test_source_id_type_requires_source_id() -> None:
    with pytest.raises(ValidationError):
        SourceReference(
            source_type="paper",
            source_url="https://arxiv.org/abs/2401.00001",
            source_id_type="arxiv_id",
        )


def test_legacy_source_uri_url_maps_to_source_url() -> None:
    reference = SourceReference.model_validate(
        {
            "source_type": "document",
            "source_uri": "https://docs.example.test/guide",
        }
    )

    assert reference.source_url == "https://docs.example.test/guide"
    assert reference.source_id is None
    assert "source_uri" not in reference.model_dump()


def test_legacy_source_uri_non_url_maps_to_source_id() -> None:
    reference = SourceReference.model_validate(
        {
            "source_type": "paper",
            "source_uri": "2401.00001",
        }
    )

    assert reference.source_id == "2401.00001"
    assert reference.source_url is None
    assert "source_uri" not in reference.model_dump()


def test_source_evidence_span_supports_docs_section() -> None:
    span = SourceEvidenceSpan(section="Guides / Retrieval")

    assert span.section == "Guides / Retrieval"


def test_source_evidence_span_supports_future_precise_locations() -> None:
    span = SourceEvidenceSpan(
        page=3,
        paragraph=2,
        line_start=10,
        line_end=12,
        char_start=100,
        char_end=180,
        metadata={"chunk_index": 1},
    )

    assert span.page == 3
    assert span.line_end == 12
    assert span.char_end == 180
    assert span.metadata["chunk_index"] == 1


def test_source_evidence_span_rejects_invalid_ranges() -> None:
    with pytest.raises(ValidationError):
        SourceEvidenceSpan(line_start=12, line_end=10)

    with pytest.raises(ValidationError):
        SourceEvidenceSpan(char_start=20, char_end=10)


def test_research_knowledge_memory_reference_uses_distilled_original_source() -> None:
    reference = SourceReference(
        source_type="paper",
        source_id="2401.00001",
        source_id_type="arxiv_id",
        source_url="https://arxiv.org/abs/2401.00001",
        title="Original Paper Title",
        authors=["Researcher One", "Researcher Two"],
        published_at=datetime(2024, 1, 1, tzinfo=UTC),
        retrieved_at=datetime(2026, 6, 29, tzinfo=UTC),
        evidence_span=SourceEvidenceSpan(section="Abstract"),
        citation_text="Original Paper Title (2024)",
        metadata={"distilled_into_knowledge_id": "knowledge-123"},
    )

    assert reference.source_id == "2401.00001"
    assert reference.source_id_type == "arxiv_id"
    assert reference.title == "Original Paper Title"
    assert reference.metadata["distilled_into_knowledge_id"] == "knowledge-123"
