"""Safe errors raised by the project Memory summary use case."""

from app.common.errors.app_error import AppError


class MemorySummaryUseCaseError(AppError):
    """表示跨服务的项目 Memory 概览查询失败。"""

    def __init__(self, *, error_code: str, error_reason: str) -> None:
        super().__init__(error_reason)
        self.error_code = error_code
        self.error_reason = error_reason
