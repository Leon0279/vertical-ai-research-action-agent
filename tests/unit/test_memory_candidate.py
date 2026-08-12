"""Tests for the typed memory write-back candidate model."""

from app.domain.enums.memory_type import MemoryType
from app.domain.models import MemoryCandidate, SourceReference


def test_memory_candidate_defaults_and_typed_source_references() -> None:
    candidate = MemoryCandidate(
        memory_type=MemoryType.DECISION,
        summary="优先建设离线评测集。",
    )

    assert candidate.candidate_source == "run_output"
    assert candidate.payload == {}
    assert candidate.source_references == []
    assert candidate.stability is None

    reference = SourceReference(
        source_type="document",
        source_id="docs-1",
        source_id_type="docs_entry_id",
        source_url="https://docs.example/1",
    )
    candidate = MemoryCandidate(
        memory_type=MemoryType.RESEARCH_KNOWLEDGE,
        summary="文档支持该结论。",
        source_references=[reference],
    )

    assert candidate.source_references == [reference]
    assert candidate.model_dump(mode="json")["source_references"] == [
        {
            "source_type": "document",
            "sub_source_type": None,
            "source_id": "docs-1",
            "source_id_type": "docs_entry_id",
            "source_url": "https://docs.example/1",
            "title": None,
            "authors": [],
            "publisher": None,
            "published_at": None,
            "retrieved_at": None,
            "evidence_span": None,
            "citation_text": None,
            "source_ref_id": None,
            "metadata": {},
        }
    ]

