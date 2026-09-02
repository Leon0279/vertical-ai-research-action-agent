"""Errors for the arXiv paper search adapter."""

from __future__ import annotations


class ArxivPaperSearchClientError(RuntimeError):
    """表示arXiv论文搜索客户端执行过程中发生的错误。

Raised when arXiv paper search fails or returns invalid data."""

    def __init__(
        self,
        message: str,
        *,
        stage: str = "configuration",
        error_category: str = "config_error",
        failure_reason: str = "invalid_request",
        status_code: int | None = None,
        retryable: bool = False,
        cause_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.error_category = error_category
        self.failure_reason = failure_reason
        self.status_code = status_code
        self.retryable = retryable
        self.cause_type = cause_type
