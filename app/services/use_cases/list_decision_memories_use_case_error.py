"""Safe errors raised by the Decision Memory list use case."""

from app.common.errors.app_error import AppError


class ListDecisionMemoriesUseCaseError(AppError):
    """表示跨服务的 Decision Memory 列表用例执行失败。"""

    def __init__(self, *, error_code: str, error_reason: str) -> None:
        super().__init__(error_reason)
        self.error_code = error_code
        self.error_reason = error_reason
