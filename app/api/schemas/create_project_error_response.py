"""Compatibility import for the former create-only project error schema."""

from app.api.schemas.project_error_response import ProjectErrorResponse

CreateProjectErrorResponse = ProjectErrorResponse

__all__ = ["CreateProjectErrorResponse"]
