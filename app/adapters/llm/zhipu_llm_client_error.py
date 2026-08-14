"""Zhipu LLM adapter errors."""

from app.common.errors.app_error import AppError


class ZhipuLLMClientError(AppError):
    """表示智谱大语言模型客户端执行过程中发生的错误。

Raised when the Zhipu LLM adapter cannot produce text."""
