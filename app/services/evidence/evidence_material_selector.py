"""Bound and select external material before LLM evidence extraction."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence

from app.adapters.embedding.contracts.embedding_client_protocol import (
    EmbeddingClientProtocol,
)
from app.domain.models import EvidenceProcessingRequest, NormalizedRetrievalItem
from app.services.evidence.models import EvidenceMaterialSelection


class EvidenceMaterialSelector:
    """Select task-relevant chunks while treating embedding as best effort."""

    _MAX_MATERIAL_CHARS = 24_000
    _CHUNK_CHARS = 6_000
    _CHUNK_OVERLAP_CHARS = 300
    _MAX_SELECTED_CHUNKS = 4
    _MAX_EMBEDDING_CHUNKS = 63
    _INTENT_FIELD_WEIGHTS = (
        ("generated_query", 4.0),
        ("target_problem", 3.0),
        ("sub_question", 2.0),
        ("gap", 2.0),
    )

    def __init__(
        self,
        embedding_client: EmbeddingClientProtocol | None,
    ) -> None:
        self._embedding_client = embedding_client

    async def select(
        self,
        request: EvidenceProcessingRequest,
        material: NormalizedRetrievalItem,
    ) -> EvidenceMaterialSelection:
        """Return full short content or a bounded selection from long content."""

        content = material.content.strip()
        if len(content) <= self._MAX_MATERIAL_CHARS:
            return EvidenceMaterialSelection(
                content=content,
                selection_method="full_content",
                original_char_count=len(content),
                selected_char_count=len(content),
                total_chunk_count=1 if content else 0,
                embedding_candidate_count=0,
                selected_chunk_count=1 if content else 0,
            )

        chunks = self._split_chunks(content)
        intent_components = self._intent_components(request)
        intent = "\n".join(value for value, _weight in intent_components)
        candidate_indexes = list(range(len(chunks)))
        if len(candidate_indexes) > self._MAX_EMBEDDING_CHUNKS:
            candidate_indexes = self._rank_lexically(
                chunks,
                intent_components,
                limit=self._MAX_EMBEDDING_CHUNKS,
            )

        degradation_reason: str | None = None
        selected_indexes: list[int]
        if self._embedding_client is None:
            degradation_reason = "embedding_client_unavailable"
            selected_indexes = self._rank_lexically(
                chunks,
                intent_components,
                limit=self._MAX_SELECTED_CHUNKS,
            )
        elif not intent:
            degradation_reason = "empty_research_intent"
            selected_indexes = self._rank_lexically(
                chunks,
                intent_components,
                limit=self._MAX_SELECTED_CHUNKS,
            )
        else:
            try:
                selected_indexes = await self._select_with_embeddings(
                    intent=intent,
                    chunks=chunks,
                    candidate_indexes=candidate_indexes,
                )
            except Exception as exc:
                degradation_reason = self._embedding_degradation_reason(exc)
                selected_indexes = self._rank_lexically(
                    chunks,
                    intent_components,
                    limit=self._MAX_SELECTED_CHUNKS,
                )

        selected_indexes = sorted(selected_indexes)
        selected_content = "\n\n".join(chunks[index] for index in selected_indexes)
        selected_content = selected_content[: self._MAX_MATERIAL_CHARS]
        return EvidenceMaterialSelection(
            content=selected_content,
            selection_method=(
                "lexical_fallback" if degradation_reason is not None else "embedding"
            ),
            original_char_count=len(content),
            selected_char_count=len(selected_content),
            total_chunk_count=len(chunks),
            embedding_candidate_count=len(candidate_indexes),
            selected_chunk_count=len(selected_indexes),
            degradation_reason=degradation_reason,
        )

    async def _select_with_embeddings(
        self,
        *,
        intent: str,
        chunks: list[str],
        candidate_indexes: list[int],
    ) -> list[int]:
        if self._embedding_client is None:
            raise RuntimeError("Embedding client is unavailable.")

        texts = [intent, *(chunks[index] for index in candidate_indexes)]
        results = await self._embedding_client.embed_texts(texts)
        vectors = self._validated_vectors(results, expected_count=len(texts))
        intent_vector = vectors[0]
        scored = [
            (
                self._cosine_similarity(intent_vector, vectors[position]),
                chunk_index,
            )
            for position, chunk_index in enumerate(candidate_indexes, start=1)
        ]
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            chunk_index
            for _score, chunk_index in scored[: self._MAX_SELECTED_CHUNKS]
        ]

    def _validated_vectors(
        self,
        results: Sequence[object],
        *,
        expected_count: int,
    ) -> list[list[float]]:
        if len(results) != expected_count:
            raise ValueError("embedding_result_count_mismatch")

        indexed: dict[int, list[float]] = {}
        dimensions: set[int] = set()
        for result in results:
            text_index = getattr(result, "text_index", None)
            embedding = getattr(result, "embedding", None)
            declared_dimensions = getattr(result, "dimensions", None)
            if not isinstance(text_index, int) or not isinstance(embedding, list):
                raise ValueError("embedding_result_shape_invalid")
            if text_index < 0 or text_index >= expected_count or text_index in indexed:
                raise ValueError("embedding_result_index_invalid")
            if not embedding or not all(isinstance(value, int | float) for value in embedding):
                raise ValueError("embedding_vector_invalid")
            vector = [float(value) for value in embedding]
            if not all(math.isfinite(value) for value in vector):
                raise ValueError("embedding_vector_invalid")
            if declared_dimensions != len(vector):
                raise ValueError("embedding_dimension_mismatch")
            if math.isclose(self._vector_norm(vector), 0.0, abs_tol=1e-12):
                raise ValueError("embedding_zero_vector")
            dimensions.add(len(vector))
            indexed[text_index] = vector

        if len(dimensions) != 1 or set(indexed) != set(range(expected_count)):
            raise ValueError("embedding_dimension_mismatch")
        return [indexed[index] for index in range(expected_count)]

    def _split_chunks(self, content: str) -> list[str]:
        chunks: list[str] = []
        start = 0
        content_length = len(content)
        preferred_minimum = self._CHUNK_CHARS // 2

        while start < content_length:
            hard_end = min(start + self._CHUNK_CHARS, content_length)
            end = hard_end
            if hard_end < content_length:
                paragraph_end = content.rfind(
                    "\n\n",
                    start + preferred_minimum,
                    hard_end,
                )
                if paragraph_end > start:
                    end = paragraph_end
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= content_length:
                break
            next_start = max(end - self._CHUNK_OVERLAP_CHARS, start + 1)
            start = next_start

        return chunks

    def _intent_components(
        self,
        request: EvidenceProcessingRequest,
    ) -> list[tuple[str, float]]:
        values = {
            "generated_query": request.retrieval_trace.generated_query,
            "target_problem": request.retrieval_trace.target_problem,
            "sub_question": request.retrieval_trace.context.get("sub_question"),
            "gap": request.retrieval_trace.context.get("gap"),
        }
        components: list[tuple[str, float]] = []
        for key, weight in self._INTENT_FIELD_WEIGHTS:
            value = values.get(key)
            if isinstance(value, str) and value.strip():
                components.append((value.strip(), weight))
        return components

    def _rank_lexically(
        self,
        chunks: list[str],
        intent_components: list[tuple[str, float]],
        *,
        limit: int,
    ) -> list[int]:
        scores = [
            (self._lexical_score(chunk, intent_components), index)
            for index, chunk in enumerate(chunks)
        ]
        if not scores:
            return []
        if all(math.isclose(score, 0.0, abs_tol=1e-12) for score, _index in scores):
            return list(range(min(limit, len(chunks))))
        scores.sort(key=lambda item: (-item[0], item[1]))
        return [index for _score, index in scores[:limit]]

    def _lexical_score(
        self,
        chunk: str,
        intent_components: list[tuple[str, float]],
    ) -> float:
        normalized_chunk = self._normalize_for_phrase(chunk)
        chunk_terms = self._lexical_terms(chunk)
        score = 0.0
        for value, weight in intent_components:
            intent_terms = self._lexical_terms(value)
            score += weight * len(chunk_terms.intersection(intent_terms))
            normalized_value = self._normalize_for_phrase(value)
            if normalized_value and normalized_value in normalized_chunk:
                score += weight * 5.0
        return score

    def _lexical_terms(self, value: str) -> set[str]:
        normalized = value.casefold()
        terms = set(re.findall(r"[a-z0-9]+", normalized))
        for sequence in re.findall(r"[\u3400-\u9fff]+", normalized):
            for size in (2, 3):
                terms.update(
                    sequence[index : index + size]
                    for index in range(max(0, len(sequence) - size + 1))
                )
        return terms

    def _normalize_for_phrase(self, value: str) -> str:
        return re.sub(r"\s+", " ", value.casefold()).strip()

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        numerator = sum(left_value * right_value for left_value, right_value in zip(left, right))
        return numerator / (self._vector_norm(left) * self._vector_norm(right))

    def _vector_norm(self, vector: list[float]) -> float:
        return math.sqrt(sum(value * value for value in vector))

    def _embedding_degradation_reason(self, error: BaseException) -> str:
        message = str(error)
        stable_reasons = {
            "embedding_result_count_mismatch",
            "embedding_result_shape_invalid",
            "embedding_result_index_invalid",
            "embedding_vector_invalid",
            "embedding_dimension_mismatch",
            "embedding_zero_vector",
        }
        if message in stable_reasons:
            return message
        error_category = getattr(error, "error_category", None)
        if isinstance(error_category, str) and error_category:
            return f"embedding_{error_category}"
        return f"embedding_{type(error).__name__}"
