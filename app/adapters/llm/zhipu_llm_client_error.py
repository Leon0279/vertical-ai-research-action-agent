"""Zhipu LLM adapter errors."""

from app.common.errors.app_error import AppError


class ZhipuLLMClientError(AppError):
    """表示智谱大语言模型客户端执行过程中发生的错误。

    Raised when the Zhipu LLM adapter cannot produce text."""

    def __init__(
        self,
        message: str,
        *,
        retriable: bool = False,
        status_code: int | None = None,
        provider_code: str | None = None,
        provider_message: str | None = None,
        request_id: str | None = None,
        finish_reason: str | None = None,
        error_category: str | None = None,
        attempt_count: int | None = None,
        max_attempts: int | None = None,
        model: str | None = None,
        response_mode: str | None = None,
        timeout_seconds: float | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format_type: str | None = None,
        thinking_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retriable = retriable
        self.status_code = status_code
        self.provider_code = provider_code
        self.provider_message = provider_message
        self.request_id = request_id
        self.finish_reason = finish_reason
        self.error_category = error_category
        self.attempt_count = attempt_count
        self.max_attempts = max_attempts
        self.model = model
        self.response_mode = response_mode
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.response_format_type = response_format_type
        self.thinking_type = thinking_type

    def attach_call_diagnostics(
        self,
        *,
        attempt_count: int,
        max_attempts: int,
        model: str,
        response_mode: str,
        timeout_seconds: float,
        temperature: float,
        max_tokens: int,
        response_format_type: str | None,
        thinking_type: str | None,
    ) -> None:
        """Attach safe request metadata before the terminal error leaves the adapter."""

        self.attempt_count = attempt_count
        self.max_attempts = max_attempts
        self.model = model
        self.response_mode = response_mode
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.response_format_type = response_format_type
        self.thinking_type = thinking_type
