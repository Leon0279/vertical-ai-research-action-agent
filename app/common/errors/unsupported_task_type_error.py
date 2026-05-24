"""Unsupported task type error."""

from app.common.errors.app_error import AppError


class UnsupportedTaskTypeError(AppError):
    """Raised when a task type cannot be routed."""

