"""Safe errors raised by Session Memory application services."""

from app.common.errors.app_error import AppError


class SessionMemoryServiceError(AppError):
    """Represent a stable Session Memory query failure."""

    def __init__(self, *, error_code: str, error_reason: str) -> None:
        super().__init__(error_reason)
        self.error_code = error_code
        self.error_reason = error_reason
