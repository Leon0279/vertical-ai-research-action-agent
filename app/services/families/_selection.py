"""Private helper for common family tool-selection policy."""

from __future__ import annotations


def select_preferred_or_default_tool(
    preferred_tool: str | None,
    default_tool_id: str,
    candidate_tools: list[str],
) -> str | None:
    """按显式偏好优先、默认工具兜底的既定 family 策略选择工具。"""

    if preferred_tool is None:
        return default_tool_id if default_tool_id in candidate_tools else None
    return preferred_tool if preferred_tool in candidate_tools else None
