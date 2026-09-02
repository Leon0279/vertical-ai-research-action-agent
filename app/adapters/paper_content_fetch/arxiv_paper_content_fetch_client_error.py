"""Error type for the arXiv paper content fetch adapter."""

from __future__ import annotations


class ArxivPaperContentFetchClientError(RuntimeError):
    """表示arXiv论文内容获取客户端执行过程中发生的错误。

Raised when arXiv PDF content fetch configuration or inputs are invalid."""

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
        response_content_type: str | None = None,
        download_bytes: int | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.error_category = error_category
        self.failure_reason = failure_reason
        self.status_code = status_code
        self.retryable = retryable
        self.cause_type = cause_type
        self.response_content_type = response_content_type
        self.download_bytes = download_bytes
