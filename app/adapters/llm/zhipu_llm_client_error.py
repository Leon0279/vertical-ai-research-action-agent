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
        request_id: str | None = None,
        finish_reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retriable = retriable
        self.status_code = status_code
        self.provider_code = provider_code
        self.request_id = request_id
        self.finish_reason = finish_reason
