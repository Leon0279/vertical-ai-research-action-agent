"""Zhipu LLM adapter implementation."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.adapters.llm.zhipu_llm_client_config import ZhipuLLMClientConfig
from app.adapters.llm.zhipu_llm_client_error import ZhipuLLMClientError


class ZhipuLLMClient(LLMClientProtocol):
    """HTTP client for Zhipu chat completions."""

    def __init__(
        self,
        config: ZhipuLLMClientConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or ZhipuLLMClientConfig.from_env()
        self._http_client = http_client

    async def generate_text(self, prompt: str) -> str:
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ZhipuLLMClientError("Prompt must not be empty.")

        response_data = await self._post_chat_completion(normalized_prompt)
        return self._extract_text(response_data)

    async def _post_chat_completion(self, prompt: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._config.base_url.rstrip('/')}/chat/completions"

        try:
            if self._http_client:
                response = await self._http_client.post(url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
                    response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise ZhipuLLMClientError("Zhipu LLM request timed out.") from exc
        except httpx.RequestError as exc:
            raise ZhipuLLMClientError(f"Zhipu LLM request failed: {exc}") from exc

        if response.status_code < 200 or response.status_code >= 300:
            request_id = response.headers.get("x-request-id") or response.headers.get("x-zhipu-request-id")
            request_note = f" request_id={request_id}" if request_id else ""
            raise ZhipuLLMClientError(
                f"Zhipu LLM request failed with status {response.status_code}.{request_note}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ZhipuLLMClientError("Zhipu LLM response was not valid JSON.") from exc

        if not isinstance(data, dict):
            raise ZhipuLLMClientError("Zhipu LLM response JSON must be an object.")
        return data

    def _extract_text(self, data: dict[str, Any]) -> str:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ZhipuLLMClientError("Zhipu LLM response did not include choices.")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ZhipuLLMClientError("Zhipu LLM response choice must be an object.")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ZhipuLLMClientError("Zhipu LLM response choice did not include a message.")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ZhipuLLMClientError("Zhipu LLM response message did not include text content.")
        return content
