"""Zhipu LLM adapter implementation."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.adapters.llm.zhipu_llm_client_config import ZhipuLLMClientConfig
from app.adapters.llm.zhipu_llm_client_error import ZhipuLLMClientError


class ZhipuLLMClient(LLMClientProtocol):
    """封装智谱聊天补全接口的 HTTP 调用。

HTTP client for Zhipu chat completions."""

    def __init__(
        self,
        config: ZhipuLLMClientConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or ZhipuLLMClientConfig.from_env()
        self._http_client = http_client

    async def generate_text(self, prompt: str) -> str:
        """Generate unconstrained text without requesting JSON mode."""

        result = await self._generate(prompt, json_object=False)
        if not isinstance(result, str):
            raise ZhipuLLMClientError("Zhipu LLM text generation returned an invalid result.")
        return result

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        """Generate and parse a JSON object using provider JSON mode."""

        result = await self._generate(prompt, json_object=True)
        if not isinstance(result, dict):
            raise ZhipuLLMClientError(
                "Zhipu LLM JSON generation returned an invalid result."
            )
        return result

    async def _generate(
        self,
        prompt: str,
        *,
        json_object: bool,
    ) -> str | dict[str, Any]:
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ZhipuLLMClientError("Prompt must not be empty.")

        attempts = self._config.max_retries + 1
        for attempt_index in range(attempts):
            try:
                response_data = await self._post_chat_completion(
                    normalized_prompt,
                    json_object=json_object,
                )
                content = self._extract_text(response_data)
                if json_object:
                    return self._parse_json_object(content, response_data)
                return content
            except ZhipuLLMClientError as exc:
                if not exc.retriable or attempt_index >= attempts - 1:
                    raise
                await asyncio.sleep(0.25 * (2**attempt_index))

        raise ZhipuLLMClientError("Zhipu LLM request exhausted its retry budget.")

    async def _post_chat_completion(
        self,
        prompt: str,
        *,
        json_object: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "stream": False,
        }
        if json_object:
            payload["response_format"] = {"type": "json_object"}
            payload["thinking"] = {"type": "disabled"}
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
            raise ZhipuLLMClientError(
                "Zhipu LLM request timed out.",
                retriable=True,
            ) from exc
        except httpx.RequestError as exc:
            raise ZhipuLLMClientError(
                f"Zhipu LLM request failed: {self._safe_text(str(exc), prompt)}",
                retriable=True,
            ) from exc

        if response.status_code < 200 or response.status_code >= 300:
            request_id = self._request_id(response)
            provider_code, provider_message = self._provider_error_details(
                response,
                prompt,
            )
            notes = [f"status {response.status_code}"]
            if provider_code:
                notes.append(f"provider_code={provider_code}")
            if provider_message:
                notes.append(f"provider_message={provider_message}")
            if request_id:
                notes.append(f"request_id={request_id}")
            raise ZhipuLLMClientError(
                "Zhipu LLM request failed with " + " ".join(notes) + ".",
                retriable=response.status_code == 429 or response.status_code >= 500,
                status_code=response.status_code,
                provider_code=provider_code,
                request_id=request_id,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ZhipuLLMClientError(
                "Zhipu LLM response was not valid JSON.",
                retriable=True,
                request_id=self._request_id(response),
            ) from exc

        if not isinstance(data, dict):
            raise ZhipuLLMClientError(
                "Zhipu LLM response JSON must be an object.",
                retriable=True,
                request_id=self._request_id(response),
            )
        return data

    def _extract_text(self, data: dict[str, Any]) -> str:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ZhipuLLMClientError(
                "Zhipu LLM response did not include choices.",
                retriable=True,
            )

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ZhipuLLMClientError(
                "Zhipu LLM response choice must be an object.",
                retriable=True,
            )

        finish_reason = self._optional_text(first_choice.get("finish_reason"))

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ZhipuLLMClientError(
                self._content_error_message(finish_reason),
                retriable=True,
                finish_reason=finish_reason,
            )

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ZhipuLLMClientError(
                self._content_error_message(finish_reason),
                retriable=True,
                finish_reason=finish_reason,
            )
        return content

    def _parse_json_object(
        self,
        content: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ZhipuLLMClientError(
                "Zhipu LLM response content was not valid JSON.",
                retriable=True,
                finish_reason=self._finish_reason(data),
            ) from exc
        if not isinstance(payload, dict):
            raise ZhipuLLMClientError(
                "Zhipu LLM response content must be a JSON object.",
                retriable=True,
                finish_reason=self._finish_reason(data),
            )
        return payload

    def _provider_error_details(
        self,
        response: httpx.Response,
        prompt: str,
    ) -> tuple[str | None, str | None]:
        try:
            payload = response.json()
        except ValueError:
            return None, None
        if not isinstance(payload, dict):
            return None, None

        error = payload.get("error")
        if isinstance(error, dict):
            code = self._optional_text(error.get("code"))
            message = self._optional_text(error.get("message"))
            return self._safe_text(code), self._safe_text(message, prompt)
        return None, self._safe_text(self._optional_text(error), prompt)

    def _safe_text(
        self,
        value: str | None,
        prompt: str | None = None,
    ) -> str | None:
        if not value:
            return None
        sanitized = " ".join(value.split())
        if self._config.api_key:
            sanitized = sanitized.replace(self._config.api_key, "[REDACTED]")
        if prompt:
            sanitized = sanitized.replace(prompt, "[REDACTED_PROMPT]")
        return sanitized[:300]

    @staticmethod
    def _optional_text(value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, int):
            return str(value)
        return None

    @staticmethod
    def _request_id(response: httpx.Response) -> str | None:
        return response.headers.get("x-request-id") or response.headers.get(
            "x-zhipu-request-id"
        )

    def _finish_reason(self, data: dict[str, Any]) -> str | None:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return None
        return self._optional_text(first_choice.get("finish_reason"))

    @staticmethod
    def _content_error_message(finish_reason: str | None) -> str:
        message = "Zhipu LLM response message did not include text content."
        if finish_reason:
            return f"{message} finish_reason={finish_reason}"
        return message
