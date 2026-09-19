"""Safe errors raised by Action Memory application services."""

from app.common.errors.app_error import AppError


class ActionMemoryServiceError(AppError):
    """表示 ActionMemoryService 无法完成查询的安全业务异常。"""

    def __init__(self, *, error_code: str, error_reason: str) -> None:
        super().__init__(error_reason)
        self.error_code = error_code
        self.error_reason = error_reason
