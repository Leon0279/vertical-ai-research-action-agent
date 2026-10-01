"""Tests for bounded external Evidence Processing material selection."""

from __future__ import annotations

import asyncio

import pytest

from app.domain.enums import AcquisitionStatus, FamilyName
from app.domain.models import (
    EmbeddingResult,
    EvidenceProcessingRequest,
    NormalizedRetrievalItem,
    RetrievalTrace,
    SourceReference,
)
from app.services.evidence.evidence_material_selector import EvidenceMaterialSelector


class FakeEmbeddingClient:
    def __init__(self, *, failure_mode: str | None = None) -> None:
        self.failure_mode = failure_mode
        self.batches: list[list[str]] = []

    async def embed_text(self, text: str) -> EmbeddingResult:
        return (await self.embed_texts([text]))[0]

    async def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        self.batches.append(texts)
        if self.failure_mode == "timeout":
            raise TimeoutError("embedding timeout")
        if self.failure_mode == "count":
            texts = texts[:-1]

        results: list[EmbeddingResult] = []
        for index, text in enumerate(texts):
            if self.failure_mode == "dimension" and index == len(texts) - 1:
                vector = [1.0, 0.0, 0.0]
            elif self.failure_mode == "zero" and index == 1:
                vector = [0.0, 0.0]
            elif index == 0 or "RELEVANT_MARKER" in text:
                vector = [1.0, 0.0]
            else:
                vector = [0.0, 1.0]
            results.append(
                EmbeddingResult(
                    text_index=index,
                    embedding=vector,
                    model="fake-embedding",
                    dimensions=len(vector),
                )
            )
        return results


def _request(
    *,
    generated_query: str = "reinforcement learning policy optimization",
    target_problem: str = "Explain reinforcement learning",
    sub_question: str = "How is a policy optimized?",
    gap: str = "policy gradient evidence",
) -> EvidenceProcessingRequest:
    return EvidenceProcessingRequest(
        acquisition_status=AcquisitionStatus.SUCCESS,
        retrieval_trace=RetrievalTrace(
            generated_query=generated_query,
            target_problem=target_problem,
            context={"sub_question": sub_question, "gap": gap},
        ),
    )


def _material(content: str) -> NormalizedRetrievalItem:
    return NormalizedRetrievalItem(
        item_id="paper-1",
        source_family=FamilyName.PAPER_SEARCH,
        source_references=[
            SourceReference(source_type="paper", source_id="paper-1")
        ],
        content=content,
    )


def _select(
    selector: EvidenceMaterialSelector,
    content: str,
    *,
    request: EvidenceProcessingRequest | None = None,
):
    return asyncio.run(selector.select(request or _request(), _material(content)))


def test_short_material_uses_full_content_without_embedding() -> None:
    embedding = FakeEmbeddingClient(failure_mode="timeout")
    selector = EvidenceMaterialSelector(embedding)
    content = "Short source-grounded evidence."

    result = _select(selector, content)

    assert result.selection_method == "full_content"
    assert result.content == content
    assert result.selected_char_count == len(content)
    assert embedding.batches == []


def test_long_material_chunks_are_bounded_and_overlap() -> None:
    selector = EvidenceMaterialSelector(None)
    content = "A" * 8_000 + "\n\n" + "B" * 8_000 + "\n\n" + "C" * 8_500

    chunks = selector._split_chunks(content)  # noqa: SLF001 - focused unit coverage

    assert len(chunks) > 4
    assert all(0 < len(chunk) <= 6_000 for chunk in chunks)
    assert all(
        left[-300:] == right[:300]
        for left, right in zip(chunks, chunks[1:])
    )


def test_long_material_uses_embedding_to_select_a_later_relevant_chunk() -> None:
    embedding = FakeEmbeddingClient()
    selector = EvidenceMaterialSelector(embedding)
    content = (
        "early unrelated material " * 1_300
        + "\n\nRELEVANT_MARKER policy optimization evidence "
        + "relevant explanation " * 400
        + "\n\nlate unrelated material " * 800
    )

    result = _select(selector, content)

    assert result.selection_method == "embedding"
    assert "RELEVANT_MARKER" in result.content
    assert result.original_char_count > 24_000
    assert result.selected_char_count <= 24_000
    assert result.selected_chunk_count <= 4
    assert len(embedding.batches) == 1


def test_embedding_ties_use_source_position_and_output_restores_source_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selector = EvidenceMaterialSelector(FakeEmbeddingClient())
    chunks = [
        "chunk zero",
        "chunk one",
        "chunk two",
        "chunk three",
        "RELEVANT_MARKER chunk four",
        "chunk five",
    ]
    monkeypatch.setattr(selector, "_split_chunks", lambda _content: chunks)

    result = _select(selector, "x" * 24_001)

    assert result.selection_method == "embedding"
    assert result.content.split("\n\n") == [
        "chunk zero",
        "chunk one",
        "chunk two",
        "RELEVANT_MARKER chunk four",
    ]


def test_embedding_batch_is_bounded_to_intent_plus_63_chunks() -> None:
    embedding = FakeEmbeddingClient()
    selector = EvidenceMaterialSelector(embedding)
    content = "unrelated block " * 30_000

    result = _select(selector, content)

    assert result.total_chunk_count > 63
    assert result.embedding_candidate_count == 63
    assert len(embedding.batches[0]) == 64


@pytest.mark.parametrize(
    ("failure_mode", "expected_reason"),
    [
        ("timeout", "embedding_TimeoutError"),
        ("count", "embedding_result_count_mismatch"),
        ("dimension", "embedding_dimension_mismatch"),
        ("zero", "embedding_zero_vector"),
    ],
)
def test_embedding_failures_degrade_to_lexical_selection(
    failure_mode: str,
    expected_reason: str,
) -> None:
    selector = EvidenceMaterialSelector(FakeEmbeddingClient(failure_mode=failure_mode))
    content = (
        "irrelevant filler " * 1_500
        + "\n\npolicy gradient evidence improves policy optimization " * 500
    )

    result = _select(selector, content)

    assert result.selection_method == "lexical_fallback"
    assert result.degradation_reason == expected_reason
    assert "policy gradient evidence" in result.content
    assert result.selected_char_count <= 24_000


def test_lexical_scoring_supports_english_chinese_and_phrase_bonus() -> None:
    selector = EvidenceMaterialSelector(None)
    chunks = [
        "unrelated introduction",
        "policy gradient evidence for reinforcement learning",
        "强化学习策略优化依赖奖励信号",
    ]

    english = selector._rank_lexically(  # noqa: SLF001 - focused unit coverage
        chunks,
        [("policy gradient evidence", 4.0)],
        limit=1,
    )
    chinese = selector._rank_lexically(  # noqa: SLF001 - focused unit coverage
        chunks,
        [("强化学习策略优化", 4.0)],
        limit=1,
    )

    assert english == [1]
    assert chinese == [2]


def test_no_lexical_match_falls_back_to_first_four_chunks() -> None:
    selector = EvidenceMaterialSelector(None)

    selected = selector._rank_lexically(  # noqa: SLF001 - focused unit coverage
        [f"chunk-{index}" for index in range(6)],
        [("completely different", 4.0)],
        limit=4,
    )

    assert selected == [0, 1, 2, 3]
