"""Execution guardrail settings."""

from dataclasses import dataclass


@dataclass(slots=True)
class ExecutionGuardrails:
    """Budget and boundary settings for research execution."""

    max_iterations: int = 2
    max_tool_calls: int = 5
    max_evidence_items: int = 20

