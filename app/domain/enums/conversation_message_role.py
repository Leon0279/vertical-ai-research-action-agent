"""Conversation message role values."""

from enum import StrEnum


class ConversationMessageRole(StrEnum):
    """表示一条持久化 conversation message 的发送方角色。"""

    # 用户提交给系统的消息。
    USER = "user"

    # 系统最终返回给用户的 assistant 消息。
    ASSISTANT = "assistant"

    # 系统级说明或控制消息。
    SYSTEM = "system"

    # 工具执行产生且被明确选择持久化的消息。
    TOOL = "tool"
