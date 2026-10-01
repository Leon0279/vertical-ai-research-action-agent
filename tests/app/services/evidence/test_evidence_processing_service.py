"""EvidenceProcessingService tests."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import pytest

from app.adapters.llm.zhipu_llm_client_error import ZhipuLLMClientError
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

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        response = await self.generate_text(prompt)
        try:
            payload = json.loads(response)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM response was not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValueError("LLM response must be a JSON object.")
        return payload


class EchoEvidenceLLMClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate_text(self, prompt: str) -> str:
        raise AssertionError("Evidence Processing must use the JSON object method.")

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        self.prompts.append(prompt)
        content = _prompt_input(prompt)["material"]["content"]
        return {
            "decision": "keep",
            "evidence_units": [
                {
                    "content": content[:1_200],
                    "evidence_type": "supporting_signal",
                }
            ],
        }


def _echo_service() -> EvidenceProcessingService:
    return EvidenceProcessingService(llm_client=EchoEvidenceLLMClient())


def _process(service: EvidenceProcessingService, request: EvidenceProcessingRequest):
    return asyncio.run(service.process(request))


def _prompt_input(prompt: str) -> dict:
    return json.loads(prompt.split("输入 JSON：\n", maxsplit=1)[1])


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
        _echo_service(),
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
        _echo_service(),
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
        _echo_service(),
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
        _echo_service(),
        _request(
            [
                _item("1", "doc1", "Hybrid retrieval is a useful baseline."),
                _item("2", "doc2", "Hybrid retrieval is a useful baseline."),
            ]
        ),
    )

    assert result.evidence_processing_summary["deduped_material_count"] == 2
    assert result.evidence_processing_summary["removed_duplicate_count"] == 0


def test_memory_passthrough_generates_processed_evidence_unit_without_llm() -> None:
    result = _process(
        EvidenceProcessingService(),
        _request(
            [
                _item(
                    "1",
                    "doc1",
                    "Hybrid retrieval is a useful baseline.",
                    source_family="research_knowledge_recall",
                )
            ]
        ),
    )

    unit = result.processed_evidence_units[0]
    assert unit.evidence_unit_id == "ev_001"
    assert unit.source_references[0].source_id == "doc1"
    assert unit.source_family == FamilyName.RESEARCH_KNOWLEDGE_RECALL
    assert unit.evidence_type == "supporting_signal"
    assert unit.target_problem == "Choose a retrieval baseline"
    assert unit.evidence_goal == "establish_coverage"
    assert unit.metadata["structuring_method"] == "memory_passthrough"
    assert unit.metadata["selected_tool"] == "tool_v1"
    assert unit.metadata["generated_query"] == "retrieval baseline docs"
    dumped = unit.model_dump()
    assert "source_ref" not in dumped
    assert "source_type" not in dumped
    assert "support_refs" not in dumped
    assert dumped["source_family"] == "research_knowledge_recall"
    assert "source_references" not in unit.metadata


def test_memory_passthrough_preserves_multiple_source_refs() -> None:
    result = _process(
        EvidenceProcessingService(),
        _request(
            [
                _item(
                    "1",
                    "doc1",
                    "Hybrid retrieval is a useful baseline.",
                    source_family="research_knowledge_recall",
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
    assert "无状态的证据材料整理任务" in llm.prompts[0]


def test_llm_prompt_uses_minimal_material_context() -> None:
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

    _process(
        service,
        _request(
            [
                _item(
                    "1",
                    "doc1",
                    "Hybrid retrieval is a useful baseline.",
                    metadata={
                        "title": "Hybrid retrieval guide",
                        "section": "Baselines",
                        "published_at": "2026-01-01",
                        "sub_source_type": "openai_api",
                        "rank": 1,
                        "score": 0.98,
                        "page_fetch_error": "debug-only",
                    },
                )
            ]
        ),
    )

    prompt_input = _prompt_input(llm.prompts[0])
    assert "无状态" in llm.prompts[0]
    assert "task_context：当前研究问题及其边界" in llm.prompts[0]
    assert "material.content：需要判断和提炼的原始材料正文" in llm.prompts[0]
    assert "dedup" not in llm.prompts[0]
    assert "provenance" not in llm.prompts[0]
    assert "retrieval family" not in llm.prompts[0]
    assert prompt_input["task_context"]["target_problem"] == "Choose a retrieval baseline"
    assert prompt_input["task_context"]["evidence_goal"] == "establish_coverage"
    assert prompt_input["material"]["content"] == "Hybrid retrieval is a useful baseline."
    assert prompt_input["material"]["source_types"] == ["document"]
    assert prompt_input["material"]["context"] == {
        "title": "Hybrid retrieval guide",
        "section": "Baselines",
        "published_at": "2026-01-01",
        "sub_source_type": "openai_api",
    }
    assert "source_ref" not in prompt_input["material"]
    assert "source_refs" not in prompt_input["material"]
    assert "source_family" not in prompt_input["material"]
    assert "metadata" not in prompt_input["material"]


def test_llm_json_object_from_adapter_is_processed() -> None:
    llm = FakeLLMClient(
        [
            """{"decision":"keep","evidence_units":[{"content":"The API supports structured outputs.","evidence_type":"direct_fact"}]}"""
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
        _echo_service(),
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


class NeverCalledEmbeddingClient:
    def __init__(self) -> None:
        self.call_count = 0

    async def embed_text(self, text: str):
        self.call_count += 1
        raise AssertionError("Embedding must not be called.")

    async def embed_texts(self, texts: list[str]):
        self.call_count += 1
        raise AssertionError("Embedding must not be called.")


class NeverCalledLLMClient:
    def __init__(self) -> None:
        self.call_count = 0

    async def generate_text(self, prompt: str) -> str:
        self.call_count += 1
        raise AssertionError("LLM must not be called.")

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        self.call_count += 1
        raise AssertionError("LLM must not be called.")


def test_memory_passthrough_never_calls_llm_or_embedding() -> None:
    llm = NeverCalledLLMClient()
    embedding = NeverCalledEmbeddingClient()
    service = EvidenceProcessingService(
        llm_client=llm,
        embedding_client=embedding,
    )

    result = _process(
        service,
        _request(
            [
                _item(
                    "memory-1",
                    "knowledge-1",
                    "Stored research knowledge remains deterministic.",
                    source_family="research_knowledge_recall",
                )
            ]
        ),
    )

    assert result.processing_status == "success"
    assert llm.call_count == 0
    assert embedding.call_count == 0


def test_short_external_material_calls_llm_but_not_embedding() -> None:
    embedding = NeverCalledEmbeddingClient()
    llm = EchoEvidenceLLMClient()
    service = EvidenceProcessingService(llm_client=llm, embedding_client=embedding)
    content = "A short external source contains a useful fact."

    result = _process(service, _request([_item("web-1", "web-1", content)]))

    assert result.processing_status == "success"
    assert embedding.call_count == 0
    assert _prompt_input(llm.prompts[0])["material"]["content"] == content


@pytest.mark.parametrize(
    "payload",
    [
        {"decision": "keep", "evidence_units": []},
        {
            "decision": "keep",
            "evidence_units": [
                {"content": "x" * 1_201, "evidence_type": "direct_fact"}
            ],
        },
        {
            "decision": "keep",
            "evidence_units": [
                {"content": f"evidence-{index}", "evidence_type": "direct_fact"}
                for index in range(4)
            ],
        },
    ],
)
def test_external_llm_output_constraints_fail_closed(payload: dict[str, Any]) -> None:
    llm = FakeLLMClient([json.dumps(payload)])

    result = _process(
        EvidenceProcessingService(llm_client=llm),
        _request([_item("web-1", "web-1", "Useful external material.")]),
    )

    assert result.processing_status == "failed"
    assert result.processed_evidence_units == []
    assert result.evidence_processing_summary.llm_invalid_output_count == 1


def test_all_normal_llm_drops_return_no_result() -> None:
    llm = FakeLLMClient(
        [json.dumps({"decision": "drop", "evidence_units": []})]
    )

    result = _process(
        EvidenceProcessingService(llm_client=llm),
        _request([_item("web-1", "web-1", "Irrelevant external material.")]),
    )

    assert result.processing_status == "no_result"
    assert result.processed_evidence_units == []


def test_memory_success_plus_external_llm_failure_is_partial_success() -> None:
    llm = FakeLLMClient(["not json"])
    service = EvidenceProcessingService(llm_client=llm)

    result = _process(
        service,
        _request(
            [
                _item(
                    "memory-1",
                    "knowledge-1",
                    "Stored knowledge is still usable.",
                    source_family="research_knowledge_recall",
                ),
                _item("web-1", "web-1", "External material fails extraction."),
            ]
        ),
    )

    assert result.processing_status == "partial_success"
    assert len(result.processed_evidence_units) == 1
    assert result.processed_evidence_units[0].source_family == (
        FamilyName.RESEARCH_KNOWLEDGE_RECALL
    )


class ConcurrencyTrackingLLMClient:
    def __init__(self) -> None:
        self.active_count = 0
        self.max_active_count = 0

    async def generate_text(self, prompt: str) -> str:
        raise AssertionError("Evidence Processing must use the JSON object method.")

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        self.active_count += 1
        self.max_active_count = max(self.max_active_count, self.active_count)
        content = _prompt_input(prompt)["material"]["content"]
        await asyncio.sleep(0.03 if content.startswith("first") else 0.005)
        self.active_count -= 1
        return {
            "decision": "keep",
            "evidence_units": [
                {"content": content, "evidence_type": "direct_fact"}
            ],
        }


def test_external_processing_limits_concurrency_and_preserves_material_order() -> None:
    llm = ConcurrencyTrackingLLMClient()
    service = EvidenceProcessingService(llm_client=llm)

    result = _process(
        service,
        _request(
            [
                _item("1", "source-1", "first source evidence"),
                _item("2", "source-2", "second source evidence"),
                _item("3", "source-3", "third source evidence"),
            ]
        ),
    )

    assert llm.max_active_count == 2
    assert [unit.content for unit in result.processed_evidence_units] == [
        "first source evidence",
        "second source evidence",
        "third source evidence",
    ]
    assert [
        unit.source_references[0].source_id
        for unit in result.processed_evidence_units
    ] == ["source-1", "source-2", "source-3"]


def test_external_material_logs_safe_selection_and_prompt_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    llm = EchoEvidenceLLMClient()
    service = EvidenceProcessingService(llm_client=llm)
    secret_material = "PRIVATE_MATERIAL_CONTENT useful fact"
    request = _request([_item("web-1", "web-1", secret_material)])
    request.retrieval_trace.generated_query = "PRIVATE_QUERY_TEXT"

    with caplog.at_level(logging.INFO, logger="app.services.evidence"):
        result = _process(service, request)

    assert result.processing_status == "success"
    events = [getattr(record, "event", None) for record in caplog.records]
    assert "evidence_processing_chunk_selection_completed" in events
    assert "evidence_processing_material_prepared" in events
    assert "evidence_processing_material_completed" in events
    assert "evidence_processing_completed" in events
    prepared = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "evidence_processing_material_prepared"
    )
    assert prepared.selection_method == "full_content"
    assert prepared.original_material_char_count == len(secret_material)
    assert prepared.llm_prompt_char_count > len(secret_material)
    serialized_records = repr([record.__dict__ for record in caplog.records])
    assert "PRIVATE_MATERIAL_CONTENT" not in serialized_records
    assert "PRIVATE_QUERY_TEXT" not in serialized_records


def test_long_external_material_logs_embedding_degradation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    embedding = NeverCalledEmbeddingClient()
    llm = EchoEvidenceLLMClient()
    service = EvidenceProcessingService(
        llm_client=llm,
        embedding_client=embedding,
    )
    content = "policy optimization evidence " * 1_200

    with caplog.at_level(logging.INFO, logger="app.services.evidence"):
        result = _process(
            service,
            _request([_item("paper-1", "paper-1", content)]),
        )

    assert result.processing_status == "success"
    degraded = next(
        record
        for record in caplog.records
        if getattr(record, "event", None)
        == "evidence_processing_chunk_selection_degraded"
    )
    assert degraded.selection_method == "lexical_fallback"
    assert degraded.embedding_fallback_reason == "embedding_AssertionError"
    assert degraded.selected_material_char_count <= 24_000
    selected_content = _prompt_input(llm.prompts[0])["material"]["content"]
    assert len(selected_content) <= 24_000
    assert selected_content != content


class FailingProviderLLMClient:
    async def generate_text(self, prompt: str) -> str:
        raise AssertionError("Evidence Processing must use the JSON object method.")

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        raise ZhipuLLMClientError(
            "safe terminal error",
            status_code=503,
            provider_code="server_error",
            provider_message="temporary provider failure",
            request_id="request-123",
            error_category="provider_server_error",
            retriable=True,
            attempt_count=3,
            max_attempts=3,
            model="glm-5.1",
            response_mode="json_object",
        )


def test_external_material_failure_logs_prompt_and_safe_provider_diagnostics(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = EvidenceProcessingService(llm_client=FailingProviderLLMClient())

    with caplog.at_level(logging.INFO, logger="app.services.evidence"):
        result = _process(
            service,
            _request([_item("web-1", "web-1", "Useful external material.")]),
        )

    assert result.processing_status == "failed"
    failed = next(
        record
        for record in caplog.records
        if getattr(record, "event", None) == "evidence_processing_material_failed"
    )
    assert failed.llm_prompt_char_count > 0
    assert failed.provider_http_status == 503
    assert failed.provider_error_code == "server_error"
    assert failed.provider_request_id == "request-123"
    assert failed.llm_attempt_count == 3
    assert failed.retryable is True
