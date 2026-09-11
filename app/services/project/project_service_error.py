"""Errors raised by project application services."""

from app.common.errors.app_error import AppError


class ProjectServiceError(AppError):
    """表示 ProjectService 无法完成某项项目操作的安全业务异常。"""

    def __init__(self, *, error_code: str, error_reason: str) -> None:
        super().__init__(error_reason)
        self.error_code = error_code
        self.error_reason = error_reason
