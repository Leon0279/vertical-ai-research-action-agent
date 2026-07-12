"""EvidenceProcessingService tests."""

from __future__ import annotations

import asyncio
import json

from app.domain.enums import AcquisitionStatus, FamilyName

from app.domain.models import (
    EvidenceProcessingRequest,
    RetrievalExecutionSummary,
    RetrievalSourceSummary,
    RetrievalTrace,
)
from app.services.evidence.evidence_processing_service import EvidenceProcessingService


class FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses.pop(0)


def _process(service: EvidenceProcessingService, request: EvidenceProcessingRequest):
    return asyncio.run(service.process(request))


def _request(
    items: list[dict],
    *,
    acquisition_status: AcquisitionStatus = AcquisitionStatus.SUCCESS,
) -> EvidenceProcessingRequest:
    return EvidenceProcessingRequest(
        normalized_items=items,
        acquisition_status=acquisition_status,
        dropped_item_count=1,
        source_summary=RetrievalSourceSummary(
            selected_family="docs_search",
            selected_tool="tool_v1",
        ),
        execution_summary=RetrievalExecutionSummary(retry_count=0),
        retrieval_trace=RetrievalTrace(
            target_problem="Choose a retrieval baseline",
            selected_family="docs_search",
            selected_tool="tool_v1",
            generated_query="retrieval baseline docs",
            context={"evidence_goal": "establish_coverage"},
        ),
    )


def _item(
    item_id: str,
    source_ref: str,
    content: str,
    *,
    source_family: str = "docs_search",
    source_type: str = "document",
    extra_source_refs: list[dict] | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "item_id": item_id,
        "source_family": source_family,
        "source_references": [
            {
                "source_type": source_type,
                "source_id": source_ref,
            },
            *(extra_source_refs or []),
        ],
        "content": content,
        "metadata": metadata or {},
    }


def test_no_result_and_failed_acquisition_short_circuit() -> None:
    service = EvidenceProcessingService()

    no_result = _process(
        service,
        _request([], acquisition_status=AcquisitionStatus.NO_RESULT),
    )
    failed = _process(
        service,
        _request([_item("1", "doc1", "Useful content")], acquisition_status=AcquisitionStatus.FAILED),
    )

    assert no_result.processing_status == "no_result"
    assert no_result.processed_evidence_units == []
    assert failed.processing_status == "no_result"
    assert failed.processed_evidence_units == []


def test_empty_normalized_items_returns_no_result() -> None:
    result = _process(EvidenceProcessingService(), _request([]))

    assert result.processing_status == "no_result"
    assert result.evidence_processing_summary["input_material_count"] == 0


def test_same_item_id_deduplicates_materials() -> None:
    result = _process(
        EvidenceProcessingService(),
        _request(
            [
                _item("same", "doc1", "Hybrid retrieval is a useful baseline."),
                _item("same", "doc1", "Hybrid retrieval is a useful baseline."),
            ]
        ),
    )

    assert result.processing_status == "success"
    assert result.evidence_processing_summary["deduped_material_count"] == 1
    assert result.evidence_processing_summary["removed_duplicate_count"] == 1
    assert len(result.processed_evidence_units) == 1


def test_same_source_and_content_deduplicates_materials() -> None:
    result = _process(
        EvidenceProcessingService(),
        _request(
            [
                _item("1", "doc1", "Hybrid retrieval is a useful baseline."),
                _item("2", "doc1", " hybrid   retrieval is a useful baseline! "),
            ]
        ),
    )

    assert result.evidence_processing_summary["deduped_material_count"] == 1
    assert result.evidence_processing_summary["exact_duplicate_removed"] == 1


def test_same_source_containment_keeps_longer_material() -> None:
    result = _process(
        EvidenceProcessingService(),
        _request(
            [
                _item("1", "doc1", "Hybrid retrieval is a baseline."),
                _item(
                    "2",
                    "doc1",
                    "Hybrid retrieval is a baseline for retrieval augmented generation.",
                ),
            ]
        ),
    )

    assert result.evidence_processing_summary["deduped_material_count"] == 1
    assert result.evidence_processing_summary["high_overlap_removed"] == 1
    assert (
        result.processed_evidence_units[0].content
        == "Hybrid retrieval is a baseline for retrieval augmented generation."
    )


def test_material_dedup_does_not_cross_sources() -> None:
    result = _process(
        EvidenceProcessingService(),
        _request(
            [
                _item("1", "doc1", "Hybrid retrieval is a useful baseline."),
                _item("2", "doc2", "Hybrid retrieval is a useful baseline."),
            ]
        ),
    )

    assert result.evidence_processing_summary["deduped_material_count"] == 2
    assert result.evidence_processing_summary["removed_duplicate_count"] == 0


def test_deterministic_fallback_generates_processed_evidence_unit() -> None:
    result = _process(
        EvidenceProcessingService(),
        _request([_item("1", "doc1", "Hybrid retrieval is a useful baseline.")]),
    )

    unit = result.processed_evidence_units[0]
    assert unit.evidence_unit_id == "ev_001"
    assert unit.source_references[0].source_id == "doc1"
    assert unit.source_family == FamilyName.DOCS_SEARCH
    assert unit.evidence_type == "supporting_signal"
    assert unit.target_problem == "Choose a retrieval baseline"
    assert unit.evidence_goal == "establish_coverage"
    assert unit.metadata["structuring_method"] == "deterministic_fallback"
    assert unit.metadata["selected_tool"] == "tool_v1"
    assert unit.metadata["generated_query"] == "retrieval baseline docs"
    dumped = unit.model_dump()
    assert "source_ref" not in dumped
    assert "source_type" not in dumped
    assert "support_refs" not in dumped
    assert dumped["source_family"] == "docs_search"
    assert "source_references" not in unit.metadata


def test_deterministic_fallback_preserves_multiple_source_refs() -> None:
    result = _process(
        EvidenceProcessingService(),
        _request(
            [
                _item(
                    "1",
                    "doc1",
                    "Hybrid retrieval is a useful baseline.",
                    extra_source_refs=[
                        {
                            "source_type": "paper",
                            "source_id": "2501.00001",
                            "source_id_type": "arxiv_id",
                        }
                    ],
                )
            ]
        ),
    )

    unit = result.processed_evidence_units[0]
    assert len(unit.source_references) == 2
    assert unit.source_references[0].source_id == "doc1"
    assert unit.source_references[1].source_id == "2501.00001"
    assert unit.source_references[1].source_id_type == "arxiv_id"
    assert "source_references" not in unit.metadata
    assert result.evidence_summary["source_coverage_summary"]["source_types"] == [
        "document",
        "paper",
    ]


def test_llm_json_successfully_structures_evidence() -> None:
    llm = FakeLLMClient(
        [
            json.dumps(
                {
                    "decision": "keep",
                    "evidence_units": [
                        {
                            "content": "Hybrid retrieval is commonly used as a practical baseline.",
                            "evidence_type": "direct_fact",
                        }
                    ],
                }
            )
        ]
    )
    service = EvidenceProcessingService(llm_client=llm)

    result = _process(
        service,
        _request([_item("1", "doc1", "Hybrid retrieval is a useful baseline.")]),
    )

    assert result.processing_status == "success"
    assert result.processed_evidence_units[0].evidence_type == "direct_fact"
    assert result.processed_evidence_units[0].content.startswith("Hybrid retrieval")
    assert "Evidence Structuring" in llm.prompts[0]


def test_llm_code_fence_json_is_parsed() -> None:
    llm = FakeLLMClient(
        [
            """```json
{"decision":"keep","evidence_units":[{"content":"The API supports structured outputs.","evidence_type":"direct_fact"}]}
```"""
        ]
    )
    service = EvidenceProcessingService(llm_client=llm)

    result = _process(
        service,
        _request([_item("1", "doc1", "The API supports structured outputs.")]),
    )

    assert result.processing_status == "success"
    assert result.processed_evidence_units[0].content == "The API supports structured outputs."


def test_invalid_llm_output_drops_current_material_without_crashing() -> None:
    llm = FakeLLMClient(
        [
            "not json",
            json.dumps(
                {
                    "decision": "keep",
                    "evidence_units": [
                        {
                            "content": "The second material is useful.",
                            "evidence_type": "supporting_signal",
                        }
                    ],
                }
            ),
        ]
    )
    service = EvidenceProcessingService(llm_client=llm)

    result = _process(
        service,
        _request(
            [
                _item("1", "doc1", "The first material is useful."),
                _item("2", "doc2", "The second material is useful."),
            ]
        ),
    )

    assert result.processing_status == "partial_success"
    assert result.evidence_processing_summary["llm_invalid_output_count"] == 1
    assert len(result.processed_evidence_units) == 1


def test_same_type_exact_evidence_consolidates_source_references() -> None:
    llm = FakeLLMClient(
        [
            json.dumps(
                {
                    "decision": "keep",
                    "evidence_units": [
                        {
                            "content": "Hybrid retrieval is a practical baseline.",
                            "evidence_type": "direct_fact",
                        }
                    ],
                }
            ),
            json.dumps(
                {
                    "decision": "keep",
                    "evidence_units": [
                        {
                            "content": "Hybrid retrieval is a practical baseline.",
                            "evidence_type": "direct_fact",
                        }
                    ],
                }
            ),
        ]
    )
    service = EvidenceProcessingService(llm_client=llm)

    result = _process(
        service,
        _request(
            [
                _item("1", "doc1", "Hybrid retrieval baseline."),
                _item("2", "doc2", "Hybrid retrieval baseline from another source."),
            ]
        ),
    )

    assert len(result.processed_evidence_units) == 1
    unit = result.processed_evidence_units[0]
    assert [ref.source_id for ref in unit.source_references] == ["doc1", "doc2"]
    assert result.evidence_processing_summary["merged_evidence_count"] == 1


def test_different_evidence_types_do_not_consolidate() -> None:
    llm = FakeLLMClient(
        [
            json.dumps(
                {
                    "decision": "keep",
                    "evidence_units": [
                        {
                            "content": "Hybrid retrieval is a practical baseline.",
                            "evidence_type": "direct_fact",
                        }
                    ],
                }
            ),
            json.dumps(
                {
                    "decision": "keep",
                    "evidence_units": [
                        {
                            "content": "Hybrid retrieval is a practical baseline.",
                            "evidence_type": "comparison_signal",
                        }
                    ],
                }
            ),
        ]
    )
    service = EvidenceProcessingService(llm_client=llm)

    result = _process(
        service,
        _request(
            [
                _item("1", "doc1", "Hybrid retrieval baseline."),
                _item("2", "doc2", "Hybrid retrieval baseline from another source."),
            ]
        ),
    )

    assert len(result.processed_evidence_units) == 2
    assert result.evidence_processing_summary["merged_evidence_count"] == 0


def test_summary_statistics_are_populated() -> None:
    result = _process(
        EvidenceProcessingService(),
        _request(
            [
                _item("1", "doc1", "Hybrid retrieval is a useful baseline."),
                _item("2", "doc1", "Hybrid retrieval is a useful baseline."),
                _item("3", "doc2", "BM25 is a sparse retrieval baseline."),
            ]
        ),
    )

    assert result.evidence_summary["new_evidence_count"] == 2
    assert result.evidence_summary["evidence_type_breakdown"] == {
        "supporting_signal": 2
    }
    assert result.evidence_summary["source_coverage_summary"]["source_families"] == [
        "docs_search"
    ]
    assert result.evidence_processing_summary["input_material_count"] == 3
    assert result.evidence_processing_summary["deduped_material_count"] == 2
    assert result.evidence_processing_summary["output_evidence_count"] == 2
