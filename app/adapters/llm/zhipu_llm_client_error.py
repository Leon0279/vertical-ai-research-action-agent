"""Zhipu LLM adapter errors."""

from app.common.errors.app_error import AppError


class ZhipuLLMClientError(AppError):
    """Raised when the Zhipu LLM adapter cannot produce text."""
