"""Project error hierarchy."""

from app.common.errors.app_error import AppError
from app.common.errors.domain_validation_error import DomainValidationError
from app.common.errors.unsupported_task_type_error import UnsupportedTaskTypeError

__all__ = ["AppError", "DomainValidationError", "UnsupportedTaskTypeError"]
