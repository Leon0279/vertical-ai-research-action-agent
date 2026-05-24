"""Domain validation error type."""

from app.common.errors.app_error import AppError


class DomainValidationError(AppError):
    """Raised when domain invariants are violated."""

