"""Shared action lifecycle rules used by memory services."""

from __future__ import annotations


_ALLOWED_ACTION_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "todo": frozenset({"in_progress", "blocked", "done", "cancelled"}),
    "in_progress": frozenset({"blocked", "done", "cancelled"}),
    "blocked": frozenset({"in_progress", "done", "cancelled"}),
    "done": frozenset(),
    "cancelled": frozenset(),
}


def is_legal_action_status_transition(
    current_status: str,
    next_status: str,
) -> bool:
    """判断 Action Memory 是否允许从当前状态推进到目标状态。

    Args:
        current_status (str): 已持久化 action 的当前生命周期状态。
        next_status (str): candidate 显式提出的目标生命周期状态。

    Returns:
        bool: 状态迁移符合前进式状态机时返回 True，否则返回 False。
    """

    normalized_current = current_status.strip().casefold()
    normalized_next = next_status.strip().casefold()
    return normalized_next in _ALLOWED_ACTION_STATUS_TRANSITIONS.get(
        normalized_current,
        frozenset(),
    )
