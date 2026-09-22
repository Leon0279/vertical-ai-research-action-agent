"""Contract for writing and querying persistent conversation history."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import (
    ConversationMessagePage,
    ConversationSessionPage,
    ExecutionContext,
    StructuredOutput,
)


@runtime_checkable
class ConversationHistoryServiceProtocol(Protocol):
    """定义持久化对话历史的写入与分页查询契约。"""

    async def record_completed_run(
        self,
        context: ExecutionContext,
        output: StructuredOutput,
    ) -> None:
        """将本次成功 run 的用户输入和 assistant 输出写入对话历史。

        Args:
            context (ExecutionContext): 已完成 workflow 的执行上下文，提供用户、会话、项目、run 与原始请求信息。
            output (StructuredOutput): 已成功组装并准备返回给调用方的最终结构化输出。

        Returns:
            None: 会话、消息与最近活跃时间写入成功后无返回值；存储失败时抛出异常，由调用方决定降级策略。
        """
        ...

    async def list_sessions(
        self,
        *,
        user_id: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> ConversationSessionPage:
        """分页读取指定用户可回看的 session 基本信息。

        Args:
            user_id (str): 会话所属用户标识，用于隔离读取范围。
            limit (int): 本页最多返回的 session 数，取值范围为 1 到 100。
            cursor (str | None): 上一页返回的 opaque cursor；首页为 None。

        Returns:
            ConversationSessionPage: 按最近更新时间倒序排列的一页 active/archived session 及下一页 cursor。
        """
        ...

    async def list_session_messages(
        self,
        *,
        user_id: str,
        session_id: str,
        limit: int = 50,
        cursor: str | None = None,
    ) -> ConversationMessagePage:
        """分页读取指定用户 session 的历史对话消息。

        Args:
            user_id (str): 会话所属用户标识，用于隔离读取范围。
            session_id (str): 需要读取历史消息的稳定会话标识。
            limit (int): 本页最多返回的消息数，取值范围为 1 到 100。
            cursor (str | None): 上一页返回的 opaque cursor；首页为 None。

        Returns:
            ConversationMessagePage: 最近一页且页内按旧到新排列的消息，以及继续读取更早消息的 cursor。
        """
        ...
