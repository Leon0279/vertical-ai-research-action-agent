"""Safe application error for the Research Knowledge Memory list use case."""

from __future__ import annotations


class ListResearchKnowledgeMemoriesUseCaseError(RuntimeError):
    """Expose a stable error code without leaking storage diagnostics."""

    def __init__(self, *, error_code: str, error_reason: str) -> None:
        super().__init__(error_reason)
        self.error_code = error_code
        self.error_reason = error_reason
