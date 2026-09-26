"""Zhipu LLM adapter implementation."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from app.adapters.llm.contracts.llm_client_protocol import LLMClientProtocol
from app.adapters.llm.zhipu_llm_client_config import ZhipuLLMClientConfig
from app.adapters.llm.zhipu_llm_client_error import ZhipuLLMClientError
from app.common.observability import sanitize_sensitive_text


class ZhipuLLMClient(LLMClientProtocol):
    """封装智谱聊天补全接口的 HTTP 调用。

HTTP client for Zhipu chat completions."""

    def __init__(
        self,
        config: ZhipuLLMClientConfig,
        http_client: httpx.AsyncClient,
    ) -> None:
        self._config = config
        self._http_client = http_client

    async def generate_text(self, prompt: str) -> str:
        """Generate unconstrained text without requesting JSON mode."""

        result = await self._generate(prompt, json_object=False)
        if not isinstance(result, str):
            raise ZhipuLLMClientError(
                "Zhipu LLM text generation returned an invalid result.",
                error_category="invalid_response",
            )
        return result

    async def generate_json_object(self, prompt: str) -> dict[str, Any]:
        """Generate and parse a JSON object using provider JSON mode."""

        result = await self._generate(prompt, json_object=True)
        if not isinstance(result, dict):
            raise ZhipuLLMClientError(
                "Zhipu LLM JSON generation returned an invalid result.",
                error_category="invalid_response",
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
        response_mode = "json_object" if json_object else "text"
        response_format_type = "json_object" if json_object else None
        thinking_type = "disabled" if json_object else None
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
                exc.attach_call_diagnostics(
                    attempt_count=attempt_index + 1,
                    max_attempts=attempts,
                    model=self._config.model,
                    response_mode=response_mode,
                    timeout_seconds=self._config.timeout_seconds,
                    temperature=self._config.temperature,
                    max_tokens=self._config.max_tokens,
                    response_format_type=response_format_type,
                    thinking_type=thinking_type,
                )
                if not exc.retriable or attempt_index >= attempts - 1:
                    raise
                await asyncio.sleep(self._retry_delay_seconds(attempt_index))

        raise ZhipuLLMClientError(
            "Zhipu LLM request exhausted its retry budget.",
            error_category="provider_server_error",
            attempt_count=attempts,
            max_attempts=attempts,
            model=self._config.model,
            response_mode=response_mode,
            timeout_seconds=self._config.timeout_seconds,
            temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
            response_format_type=response_format_type,
            thinking_type=thinking_type,
        )

    @staticmethod
    def _retry_delay_seconds(attempt_index: int) -> float:
        """Use the bounded transient-failure backoff sequence."""

        if attempt_index <= 0:
            return 1.0
        if attempt_index == 1:
            return 3.0
        return 3.0 * (2 ** (attempt_index - 1))

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
            response = await self._http_client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise ZhipuLLMClientError(
                "Zhipu LLM request timed out.",
                retriable=True,
                error_category="timeout",
            ) from exc
        except httpx.RequestError as exc:
            raise ZhipuLLMClientError(
                f"Zhipu LLM request failed: {self._safe_text(str(exc), prompt)}",
                retriable=True,
                error_category="network",
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
                provider_message=provider_message,
                request_id=request_id,
                error_category=self._http_error_category(response.status_code),
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise ZhipuLLMClientError(
                "Zhipu LLM response was not valid JSON.",
                request_id=self._request_id(response),
                error_category="invalid_response",
            ) from exc

        if not isinstance(data, dict):
            raise ZhipuLLMClientError(
                "Zhipu LLM response JSON must be an object.",
                request_id=self._request_id(response),
                error_category="invalid_response",
            )
        return data

    def _extract_text(self, data: dict[str, Any]) -> str:
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ZhipuLLMClientError(
                "Zhipu LLM response did not include choices.",
                error_category="invalid_response",
            )

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ZhipuLLMClientError(
                "Zhipu LLM response choice must be an object.",
                error_category="invalid_response",
            )

        finish_reason = self._optional_text(first_choice.get("finish_reason"))

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ZhipuLLMClientError(
                self._content_error_message(finish_reason),
                finish_reason=finish_reason,
                error_category="empty_content",
            )

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ZhipuLLMClientError(
                self._content_error_message(finish_reason),
                finish_reason=finish_reason,
                error_category="empty_content",
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
                finish_reason=self._finish_reason(data),
                error_category="invalid_json",
            ) from exc
        if not isinstance(payload, dict):
            raise ZhipuLLMClientError(
                "Zhipu LLM response content must be a JSON object.",
                finish_reason=self._finish_reason(data),
                error_category="invalid_json",
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
            normalized_prompt = " ".join(prompt.split())
            sanitized = sanitized.replace(normalized_prompt, "[REDACTED_PROMPT]")
            if self._contains_prompt_overlap(sanitized, normalized_prompt):
                sanitized = "[REDACTED_PROMPT_CONTENT]"
        return sanitize_sensitive_text(sanitized, max_length=300)

    @staticmethod
    def _contains_prompt_overlap(value: str, prompt: str) -> bool:
        """Reject provider messages that echo a meaningful prompt fragment."""

        minimum_overlap = min(12, len(prompt))
        if minimum_overlap <= 0 or len(value) < minimum_overlap:
            return False
        prompt_fragments = {
            prompt[index : index + minimum_overlap]
            for index in range(len(prompt) - minimum_overlap + 1)
        }
        return any(
            value[index : index + minimum_overlap] in prompt_fragments
            for index in range(len(value) - minimum_overlap + 1)
        )

    @staticmethod
    def _http_error_category(status_code: int) -> str:
        if status_code == 429:
            return "rate_limit"
        if status_code >= 500:
            return "provider_server_error"
        return "provider_client_error"

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
