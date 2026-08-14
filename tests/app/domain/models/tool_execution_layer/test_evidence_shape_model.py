"""EvidenceShape model tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.models import EvidenceShape


def test_evidence_shape_defaults_are_neutral() -> None:
    shape = EvidenceShape()

    assert shape.desired_evidence_kind == "supporting_evidence"
    assert shape.freshness_requirement == "normal"
    assert shape.breadth == "normal"


def test_evidence_shape_accepts_lld_recommended_values() -> None:
    shape = EvidenceShape(
        desired_evidence_kind="direct_fact",
        freshness_requirement="fresh_preferred",
        breadth="narrow",
    )

    assert shape.model_dump() == {
        "desired_evidence_kind": "direct_fact",
        "freshness_requirement": "fresh_preferred",
        "breadth": "narrow",
    }


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("desired_evidence_kind", "primary_source"),
        ("freshness_requirement", "latest_only"),
        ("breadth", "global"),
    ],
)
def test_evidence_shape_rejects_invalid_values(field_name: str, bad_value: str) -> None:
    payload = EvidenceShape().model_dump()
    payload[field_name] = bad_value

    with pytest.raises(ValidationError):
        EvidenceShape(**payload)
