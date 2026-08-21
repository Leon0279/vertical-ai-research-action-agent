"""EvidenceCoverageEntry unit tests."""

import pytest
from pydantic import ValidationError

from app.services.executor.models.evidence_coverage_entry import (
    EvidenceCoverageEntry,
)


def test_evidence_coverage_entry_has_safe_defaults_and_json_dump() -> None:
    entry = EvidenceCoverageEntry(
        target_type="objective",
        target_text="Assess the retrieval design.",
        coverage_status="not_covered",
        coverage_summary="尚未完成语义覆盖判断。",
    )

    assert entry.retrieved_evidence_keys == []
    assert entry.supporting_evidence_keys == []
    assert entry.uncovered_aspects == []
    assert entry.model_dump(mode="json") == {
        "target_type": "objective",
        "target_text": "Assess the retrieval design.",
        "coverage_status": "not_covered",
        "retrieved_evidence_keys": [],
        "supporting_evidence_keys": [],
        "uncovered_aspects": [],
        "coverage_summary": "尚未完成语义覆盖判断。",
    }


def test_evidence_coverage_entry_rejects_unknown_fields_and_empty_summary() -> None:
    with pytest.raises(ValidationError):
        EvidenceCoverageEntry(
            target_type="objective",
            target_text="Assess the retrieval design.",
            coverage_status="not_covered",
            coverage_summary="",
            unknown_field="not allowed",
        )
