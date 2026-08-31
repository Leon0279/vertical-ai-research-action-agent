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
    monkeypatch.setenv("ZHIPU_MAX_RETRIES", "2")

    config = ZhipuLLMClientConfig.from_env()

    assert config.api_key == "env-key"
    assert config.base_url == "https://example.test/api"
    assert config.model == "glm-test"
    assert config.timeout_seconds == 9.5
    assert config.temperature == 0.7
    assert config.max_tokens == 88
    assert config.max_retries == 2


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


def test_generate_json_object_posts_expected_payload_and_returns_dict() -> None:
    seen_request: httpx.Request | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_request
        seen_request = request
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"result":"adapter result"}'}}]},
        )

    async def run_case() -> dict[str, object]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(
                    api_key="fake-key",
                    model="glm-test",
                    temperature=0.3,
                    max_tokens=77,
                ),
                http_client=client,
            )
            return await llm_client.generate_json_object("  hello zhipu  ")

    assert asyncio.run(run_case()) == {"result": "adapter result"}
    assert seen_request is not None
    request_json = json.loads(seen_request.content.decode())
    assert request_json == {
        "model": "glm-test",
        "messages": [{"role": "user", "content": "hello zhipu"}],
        "temperature": 0.3,
        "max_tokens": 77,
        "stream": False,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }


def test_generate_text_rejects_empty_prompt() -> None:
    llm_client = ZhipuLLMClient(config=ZhipuLLMClientConfig(api_key="fake-key"))

    with pytest.raises(ZhipuLLMClientError, match="Prompt must not be empty"):
        asyncio.run(llm_client.generate_text("   "))

    with pytest.raises(ZhipuLLMClientError, match="Prompt must not be empty"):
        asyncio.run(llm_client.generate_json_object("   "))


@pytest.mark.parametrize("status_code", [400, 401, 403])
def test_generate_text_does_not_retry_deterministic_http_errors(
    status_code: int,
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            status_code,
            headers={"x-request-id": "req-1"},
            json={
                "error": {
                    "code": "auth_failed",
                    "message": f"unauthorized fake-key {request.content.decode()}",
                }
            },
        )

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(api_key="fake-key", max_retries=1),
                http_client=client,
            )

            await llm_client.generate_text("secret prompt")

    with pytest.raises(
        ZhipuLLMClientError,
        match=f"status {status_code}",
    ) as exc_info:
        asyncio.run(run_case())
    assert call_count == 1
    assert exc_info.value.status_code == status_code
    assert exc_info.value.provider_code == "auth_failed"
    assert exc_info.value.request_id == "req-1"
    assert "fake-key" not in str(exc_info.value)
    assert "secret prompt" not in str(exc_info.value)


def test_generate_text_rejects_missing_choices() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(200, json={"choices": []})

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(api_key="fake-key", max_retries=0),
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
                config=ZhipuLLMClientConfig(api_key="fake-key", max_retries=0),
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
                config=ZhipuLLMClientConfig(api_key="fake-key", max_retries=0),
                http_client=client,
            )

            await llm_client.generate_text("hello")

    with pytest.raises(ZhipuLLMClientError, match="timed out"):
        asyncio.run(run_case())


@pytest.mark.parametrize("status_code", [429, 503])
def test_generate_text_retries_transient_http_error_once_then_succeeds(
    status_code: int,
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        _ = request
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                status_code,
                json={"error": {"code": "busy", "message": "retry"}},
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"status":"ok"}'}}]},
        )

    async def run_case() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(api_key="fake-key", max_retries=1),
                http_client=client,
            )
            return await llm_client.generate_text("hello")

    assert asyncio.run(run_case()) == '{"status":"ok"}'
    assert call_count == 2


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.TimeoutException])
def test_generate_text_retries_request_error_once_then_succeeds(
    error_type: type[httpx.RequestError],
) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise error_type("temporary failure", request=request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"status":"ok"}'}}]},
        )

    async def run_case() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(api_key="fake-key", max_retries=1),
                http_client=client,
            )
            return await llm_client.generate_text("hello")

    assert asyncio.run(run_case()) == '{"status":"ok"}'
    assert call_count == 2


def test_generate_json_object_retries_invalid_json_content_once() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        _ = request
        call_count += 1
        content = "not-json" if call_count == 1 else '{"status":"ok"}'
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": content}}]},
        )

    async def run_case() -> dict[str, object]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(api_key="fake-key", max_retries=1),
                http_client=client,
            )
            return await llm_client.generate_json_object("hello")

    assert asyncio.run(run_case()) == {"status": "ok"}
    assert call_count == 2


def test_generate_json_object_retries_non_object_content_once() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        _ = request
        call_count += 1
        content = "[]" if call_count == 1 else '{"status":"ok"}'
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
        )

    async def run_case() -> dict[str, object]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(api_key="fake-key", max_retries=1),
                http_client=client,
            )
            return await llm_client.generate_json_object("hello")

    assert asyncio.run(run_case()) == {"status": "ok"}
    assert call_count == 2


def test_generate_text_reports_empty_content_finish_reason_without_using_reasoning() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _ = request
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": "", "reasoning_content": '{"unsafe":"fallback"}'},
                    }
                ]
            },
        )

    async def run_case() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(api_key="fake-key", max_retries=0),
                http_client=client,
            )
            await llm_client.generate_text("hello")

    with pytest.raises(ZhipuLLMClientError, match="finish_reason=length") as exc_info:
        asyncio.run(run_case())
    assert exc_info.value.finish_reason == "length"


def test_generate_text_accepts_non_json_without_retry() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        request_payload = json.loads(request.content.decode())
        assert "response_format" not in request_payload
        assert "thinking" not in request_payload
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "plain text"}}]},
        )

    async def run_case() -> str:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm_client = ZhipuLLMClient(
                config=ZhipuLLMClientConfig(api_key="fake-key", max_retries=1),
                http_client=client,
            )
            return await llm_client.generate_text("hello")

    assert asyncio.run(run_case()) == "plain text"
    assert call_count == 1
