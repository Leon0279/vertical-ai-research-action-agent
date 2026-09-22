"""Conversation message content formats."""

from enum import StrEnum


class ConversationContentFormat(StrEnum):
    """表示持久化 conversation message 正文采用的编码格式。"""

    # 普通纯文本正文。
    TEXT = "text"

    # 可由前端按 Markdown 渲染的正文。
    MARKDOWN = "markdown"

    # 正文是合法 JSON 文本。
    JSON = "json"
