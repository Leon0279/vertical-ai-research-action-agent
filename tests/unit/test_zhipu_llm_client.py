"""Zhipu LLM adapter tests."""

import asyncio
import json

import httpx
import pytest

from app.adapters.llm.zhipu_llm_client import ZhipuLLMClient
from app.adapters.llm.zhipu_llm_client_config import ZhipuLLMClientConfig
from app.adapters.llm.zhipu_llm_client_error import ZhipuLLMClientError


def test_zhipu_config_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHIPU_API_KEY", "env-key")
    monkeypatch.setenv("ZHIPU_BASE_URL", "https://example.test/api")
    monkeypatch.setenv("ZHIPU_MODEL", "glm-test")
    monkeypatch.setenv("ZHIPU_TIMEOUT_SECONDS", "9.5")
    monkeypatch.setenv("ZHIPU_TEMPERATURE", "0.7")
    monkeypatch.setenv("ZHIPU_MAX_TOKENS", "88")

    config = ZhipuLLMClientConfig.from_env()

    assert config.api_key == "env-key"
    assert config.base_url == "https://example.test/api"
    assert config.model == "glm-test"
    assert config.timeout_seconds == 9.5
    assert config.temperature == 0.7
    assert config.max_tokens == 88


def test_zhipu_config_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZHIPU_API_KEY", raising=False)

    with pytest.raises(ZhipuLLMClientError, match="ZHIPU_API_KEY"):
        ZhipuLLMClientConfig.from_env()


def test_generate_text_posts_expected_payload_and_returns_content() -> None:
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "adapter result"}}]},
        )

    async def run_case() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(
                    api_key="fake-key",
                    base_url="https://example.test/api/paas/v4/",
                    model="glm-test",
                    temperature=0.3,
                    max_tokens=77,
                ),
                http_client=client,
            )

            return await llm_client.generate_text("  hello zhipu  ")

    result = asyncio.run(run_case())

    assert result == "adapter result"
    assert seen_request is not None
    assert str(seen_request.url) == "https://example.test/api/paas/v4/chat/completions"
    assert seen_request.headers["authorization"] == "Bearer fake-key"
    assert seen_request.headers["content-type"] == "application/json"
    request_json = json.loads(seen_request.content.decode())
    assert request_json == {
        "model": "glm-test",
        "messages": [{"role": "user", "content": "hello zhipu"}],
        "temperature": 0.3,
        "max_tokens": 77,
        "stream": False,
    }


def test_generate_text_rejects_empty_prompt() -> None:
    llm_client = ZhipuLLMClient(config=ZhipuLLMClientConfig(api_key="fake-key"))

    with pytest.raises(ZhipuLLMClientError, match="Prompt must not be empty"):
        asyncio.run(llm_client.generate_text("   "))


def test_generate_text_wraps_http_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(401, headers={"x-request-id": "req-1"}, json={"error": "unauthorized"})

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(api_key="fake-key"),
                http_client=client,
            )

            await llm_client.generate_text("hello")

    with pytest.raises(ZhipuLLMClientError, match="status 401"):
        asyncio.run(run_case())


def test_generate_text_rejects_missing_choices() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json={"choices": []})

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(api_key="fake-key"),
                http_client=client,
            )

            await llm_client.generate_text("hello")

    with pytest.raises(ZhipuLLMClientError, match="choices"):
        asyncio.run(run_case())


def test_generate_text_wraps_request_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(api_key="fake-key"),
                http_client=client,
            )

            await llm_client.generate_text("hello")

    with pytest.raises(ZhipuLLMClientError, match="request failed"):
        asyncio.run(run_case())


def test_generate_text_wraps_timeout_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(api_key="fake-key"),
                http_client=client,
            )

            await llm_client.generate_text("hello")

    with pytest.raises(ZhipuLLMClientError, match="timed out"):
        asyncio.run(run_case())
