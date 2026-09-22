"""Conversation session lifecycle statuses."""

from enum import StrEnum


class ConversationSessionStatus(StrEnum):
    """表示持久化 conversation session 的生命周期状态。"""

    # 当前仍可继续追加消息的活跃会话。
    ACTIVE = "active"

    # 已归档但仍可供用户回看的历史会话。
    ARCHIVED = "archived"

    # 已软删除且默认不应出现在普通历史列表中的会话。
    DELETED = "deleted"
