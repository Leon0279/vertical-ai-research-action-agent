"""Zhipu embedding adapter tests."""

import asyncio
import json

import httpx
import pytest

from app.adapters.embedding.contracts.embedding_client_protocol import (
    EmbeddingClientProtocol,
)
from app.adapters.embedding.zhipu_embedding_client import ZhipuEmbeddingClient
from app.adapters.embedding.zhipu_embedding_client_config import (
    ZhipuEmbeddingClientConfig,
)
from app.adapters.embedding.zhipu_embedding_client_error import (
    ZhipuEmbeddingClientError,
)


def test_zhipu_embedding_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHIPU_API_KEY", "env-key")
    monkeypatch.setenv("ZHIPU_EMBEDDING_BASE_URL", "https://example.test/api")
    monkeypatch.setenv("ZHIPU_EMBEDDING_MODEL", "embedding-3")
    monkeypatch.setenv("ZHIPU_EMBEDDING_DIMENSIONS", "2048")
    monkeypatch.setenv("ZHIPU_EMBEDDING_TIMEOUT_SECONDS", "9.5")
    monkeypatch.setenv("ZHIPU_EMBEDDING_MAX_BATCH_SIZE", "12")

    config = ZhipuEmbeddingClientConfig.from_env()

    assert config.api_key == "env-key"
    assert config.base_url == "https://example.test/api"
    assert config.model == "embedding-3"
    assert config.dimensions == 2048
    assert config.timeout_seconds == 9.5
    assert config.max_batch_size == 12


def test_zhipu_embedding_config_uses_expected_defaults() -> None:
    config = ZhipuEmbeddingClientConfig(api_key="fake-key")

    assert config.base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert config.model == "embedding-3"
    assert config.dimensions == 1024
    assert config.timeout_seconds == 30.0
    assert config.max_batch_size == 64


def test_zhipu_embedding_config_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)

    with pytest.raises(ZhipuEmbeddingClientError, match="ZHIPU_API_KEY"):
        ZhipuEmbeddingClientConfig.from_env()


def test_zhipu_embedding_config_rejects_invalid_embedding_3_dimensions() -> None:
    with pytest.raises(ZhipuEmbeddingClientError, match="embedding-3 dimensions"):
        ZhipuEmbeddingClientConfig(api_key="fake-key", dimensions=768)


def test_embed_text_posts_expected_payload_and_returns_embedding() -> None:
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(
            200,
            json={
                "model": "embedding-3",
                "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}],
                "usage": {"prompt_tokens": 3, "total_tokens": 3},
            },
        )

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            embedding_client = ZhipuEmbeddingClient(
                config=ZhipuEmbeddingClientConfig(
                    api_key="fake-key",
                    base_url="https://example.test/api/paas/v4/",
                    model="embedding-3",
                    dimensions=512,
                ),
                http_client=client,
            )

            return await embedding_client.embed_text("  hello zhipu  ")

    result = asyncio.run(run_case())

    assert result.text_index == 0
    assert result.embedding == [0.1, 0.2, 0.3]
    assert result.model == "embedding-3"
    assert result.dimensions == 3
    assert result.prompt_tokens == 3
    assert result.total_tokens == 3
    assert seen_request is not None
    assert str(seen_request.url) == "https://example.test/api/paas/v4/embeddings"
    assert seen_request.headers["authorization"] == "Bearer fake-key"
    request_json = json.loads(seen_request.content.decode())
    assert request_json == {
        "model": "embedding-3",
        "input": "hello zhipu",
        "dimensions": 512,
    }


def test_embed_texts_posts_array_payload_and_returns_input_order() -> None:
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.4, 0.5]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ],
                "usage": {"prompt_tokens": 5, "total_tokens": 5},
            },
        )

    async def run_case():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            embedding_client = ZhipuEmbeddingClient(
                config=ZhipuEmbeddingClientConfig(api_key="fake-key"),
                http_client=client,
            )

            return await embedding_client.embed_texts([" first ", "second"])

    results = asyncio.run(run_case())

    assert [result.text_index for result in results] == [0, 1]
    assert [result.embedding for result in results] == [[0.1, 0.2], [0.4, 0.5]]
    assert seen_request is not None
    request_json = json.loads(seen_request.content.decode())
    assert request_json == {
        "model": "embedding-3",
        "input": ["first", "second"],
        "dimensions": 1024,
    }


def test_embedding_2_payload_omits_dimensions() -> None:
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1]}]})

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            embedding_client = ZhipuEmbeddingClient(
                config=ZhipuEmbeddingClientConfig(
                    api_key="fake-key",
                    model="embedding-2",
                    dimensions=1024,
                ),
                http_client=client,
            )

            await embedding_client.embed_text("hello")

    asyncio.run(run_case())

    assert seen_request is not None
    request_json = json.loads(seen_request.content.decode())
    assert request_json == {"model": "embedding-2", "input": "hello"}


def test_embed_text_rejects_empty_text() -> None:
    embedding_client = ZhipuEmbeddingClient(
        config=ZhipuEmbeddingClientConfig(api_key="fake-key")
    )

    with pytest.raises(ZhipuEmbeddingClientError, match="must not be empty"):
        asyncio.run(embedding_client.embed_text("   "))


def test_embed_texts_rejects_empty_or_too_large_batches() -> None:
    embedding_client = ZhipuEmbeddingClient(
        config=ZhipuEmbeddingClientConfig(api_key="fake-key", max_batch_size=1)
    )

    with pytest.raises(ZhipuEmbeddingClientError, match="must not be empty"):
        asyncio.run(embedding_client.embed_texts([]))
    with pytest.raises(ZhipuEmbeddingClientError, match="must not exceed"):
        asyncio.run(embedding_client.embed_texts(["one", "two"]))


def test_embed_text_wraps_http_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(401, headers={"x-request-id": "req-1"}, json={"error": "unauthorized"})

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            embedding_client = ZhipuEmbeddingClient(
                config=ZhipuEmbeddingClientConfig(api_key="fake-key"),
                http_client=client,
            )

            await embedding_client.embed_text("hello")

    with pytest.raises(ZhipuEmbeddingClientError, match="status 401"):
        asyncio.run(run_case())


def test_embed_text_wraps_request_and_timeout_errors() -> None:
    def request_error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    async def run_case(handler) -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            embedding_client = ZhipuEmbeddingClient(
                config=ZhipuEmbeddingClientConfig(api_key="fake-key"),
                http_client=client,
            )

            await embedding_client.embed_text("hello")

    with pytest.raises(ZhipuEmbeddingClientError, match="request failed"):
        asyncio.run(run_case(request_error_handler))
    with pytest.raises(ZhipuEmbeddingClientError, match="timed out"):
        asyncio.run(run_case(timeout_handler))


def test_embed_text_rejects_bad_response_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": ["bad"]}]})

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            embedding_client = ZhipuEmbeddingClient(
                config=ZhipuEmbeddingClientConfig(api_key="fake-key"),
                http_client=client,
            )

            await embedding_client.embed_text("hello")

    with pytest.raises(ZhipuEmbeddingClientError, match="numeric"):
        asyncio.run(run_case())


def test_embed_text_rejects_mismatched_response_count() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json={"data": []})

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            embedding_client = ZhipuEmbeddingClient(
                config=ZhipuEmbeddingClientConfig(api_key="fake-key"),
                http_client=client,
            )

            await embedding_client.embed_text("hello")

    with pytest.raises(ZhipuEmbeddingClientError, match="count"):
        asyncio.run(run_case())


def test_zhipu_embedding_client_satisfies_protocol() -> None:
    embedding_client = ZhipuEmbeddingClient(
        config=ZhipuEmbeddingClientConfig(api_key="fake-key")
    )

    assert isinstance(embedding_client, EmbeddingClientProtocol)
