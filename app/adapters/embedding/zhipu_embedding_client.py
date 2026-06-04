"""Zhipu embedding adapter implementation."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.embedding.contracts.embedding_client_protocol import (
    EmbeddingClientProtocol,
)
from app.adapters.embedding.zhipu_embedding_client_config import (
    ZhipuEmbeddingClientConfig,
)
from app.adapters.embedding.zhipu_embedding_client_error import (
    ZhipuEmbeddingClientError,
)
from app.domain.models import EmbeddingResult


class ZhipuEmbeddingClient(EmbeddingClientProtocol):
    """HTTP client for Zhipu embeddings."""

    def __init__(
        self,
        config: ZhipuEmbeddingClientConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or ZhipuEmbeddingClientConfig.from_env()
        self._http_client = http_client

    async def embed_text(self, text: str) -> EmbeddingResult:
        """Generate an embedding for one text."""

        return (await self.embed_texts([text]))[0]

    async def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        """Generate embeddings for a batch of texts."""

        normalized_texts = self._normalize_texts(texts)
        response_data = await self._post_embeddings(normalized_texts)
        return self._extract_results(response_data, expected_count=len(normalized_texts))

    def _normalize_texts(self, texts: list[str]) -> list[str]:
        if not texts:
            raise ZhipuEmbeddingClientError("Embedding input must not be empty.")
        if len(texts) > self._config.max_batch_size:
            raise ZhipuEmbeddingClientError(
                f"Embedding batch size must not exceed {self._config.max_batch_size}."
            )

        normalized_texts = [text.strip() for text in texts]
        if any(not text for text in normalized_texts):
            raise ZhipuEmbeddingClientError("Embedding text must not be empty.")
        return normalized_texts

    async def _post_embeddings(self, texts: list[str]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._config.model,
            "input": texts[0] if len(texts) == 1 else texts,
        }
        if self._config.model == "embedding-3":
            payload["dimensions"] = self._config.dimensions

        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._config.base_url.rstrip('/')}/embeddings"

        try:
            if self._http_client:
                response = await self._http_client.post(url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
                    response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise ZhipuEmbeddingClientError("Zhipu embedding request timed out.") from exc
        except httpx.RequestError as exc:
            raise ZhipuEmbeddingClientError(f"Zhipu embedding request failed: {exc}") from exc

        if response.status_code < 200 or response.status_code >= 300:
            request_id = response.headers.get("x-request-id") or response.headers.get("x-zhipu-request-id")
            request_note = f" request_id={request_id}" if request_id else ""
            raise ZhipuEmbeddingClientError(
                f"Zhipu embedding request failed with status {response.status_code}.{request_note}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ZhipuEmbeddingClientError("Zhipu embedding response was not valid JSON.") from exc

        if not isinstance(data, dict):
            raise ZhipuEmbeddingClientError("Zhipu embedding response JSON must be an object.")
        return data

    def _extract_results(
        self,
        data: dict[str, Any],
        *,
        expected_count: int,
    ) -> list[EmbeddingResult]:
        raw_items = data.get("data")
        if not isinstance(raw_items, list) or len(raw_items) != expected_count:
            raise ZhipuEmbeddingClientError(
                "Zhipu embedding response data count did not match input count."
            )

        usage = data.get("usage")
        if usage is not None and not isinstance(usage, dict):
            raise ZhipuEmbeddingClientError("Zhipu embedding response usage must be an object.")

        model = data.get("model") if isinstance(data.get("model"), str) else self._config.model
        prompt_tokens = self._optional_int(usage.get("prompt_tokens") if usage else None)
        total_tokens = self._optional_int(usage.get("total_tokens") if usage else None)

        results_by_index: dict[int, EmbeddingResult] = {}
        for item in raw_items:
            if not isinstance(item, dict):
                raise ZhipuEmbeddingClientError("Zhipu embedding response item must be an object.")

            index = item.get("index")
            if not isinstance(index, int) or index < 0 or index >= expected_count:
                raise ZhipuEmbeddingClientError("Zhipu embedding response item index is invalid.")
            if index in results_by_index:
                raise ZhipuEmbeddingClientError("Zhipu embedding response contained duplicate indexes.")

            embedding = self._extract_embedding(item)
            results_by_index[index] = EmbeddingResult(
                text_index=index,
                embedding=embedding,
                model=model,
                dimensions=len(embedding),
                prompt_tokens=prompt_tokens,
                total_tokens=total_tokens,
            )

        expected_indexes = set(range(expected_count))
        if set(results_by_index) != expected_indexes:
            raise ZhipuEmbeddingClientError("Zhipu embedding response indexes did not match inputs.")
        return [results_by_index[index] for index in range(expected_count)]

    def _extract_embedding(self, item: dict[str, Any]) -> list[float]:
        raw_embedding = item.get("embedding")
        if not isinstance(raw_embedding, list) or not raw_embedding:
            raise ZhipuEmbeddingClientError("Zhipu embedding response item did not include an embedding.")

        embedding: list[float] = []
        for value in raw_embedding:
            if not isinstance(value, int | float):
                raise ZhipuEmbeddingClientError("Zhipu embedding values must be numeric.")
            embedding.append(float(value))
        return embedding

    def _optional_int(self, value: Any) -> int | None:
        if value is None:
            return None
        if not isinstance(value, int) or value < 0:
            raise ZhipuEmbeddingClientError("Zhipu embedding usage values must be non-negative integers.")
        return value
