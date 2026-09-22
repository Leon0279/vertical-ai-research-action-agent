"""Contract for persistent conversation message logs."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.domain.models import MessageLogRecord


@runtime_checkable
class MessageLogStoreProtocol(Protocol):
    """定义 append-only conversation message history 的存储契约。"""

    async def append_message(self, message: MessageLogRecord) -> None:
        """向消息历史追加一条不可变消息。

        Args:
            message (MessageLogRecord): 待持久化的完整消息记录。

        Returns:
            None: 写入成功后无返回值；重复标识或底层存储失败时抛出异常。
        """
        ...

    async def append_messages(self, messages: list[MessageLogRecord]) -> None:
        """在同一存储事务中追加一批不可变消息。

        Args:
            messages (list[MessageLogRecord]): 按业务顺序排列的待持久化消息；空列表表示无需写入。

        Returns:
            None: 整批写入成功后无返回值；任一消息写入失败时回滚整批并抛出异常。
        """
        ...

    async def list_session_messages(
        self,
        *,
        user_id: str,
        session_id: str,
        limit: int,
        before_created_at: datetime | None = None,
        before_message_id: str | None = None,
    ) -> list[MessageLogRecord]:
        """按时间倒序读取一个 session 的一批消息。

        Args:
            user_id (str): 消息所属用户标识，用于隔离读取范围。
            session_id (str): 需要读取消息的会话标识。
            limit (int): 最大返回消息数，取值范围为 1 到 100。
            before_created_at (datetime | None): 上一页末项创建时间；首页为 None。
            before_message_id (str | None): 上一页末项消息标识；首页为 None。

        Returns:
            list[MessageLogRecord]: 按 created_at、message_id 倒序排列的消息记录。
        """
        ...

    async def list_project_messages(
        self,
        *,
        user_id: str,
        project_id: str,
        limit: int,
        before_created_at: datetime | None = None,
        before_message_id: str | None = None,
    ) -> list[MessageLogRecord]:
        """按时间倒序读取一个项目的一批消息。

        Args:
            user_id (str): 消息所属用户标识，用于隔离读取范围。
            project_id (str): 需要读取消息的稳定项目标识。
            limit (int): 最大返回消息数，取值范围为 1 到 100。
            before_created_at (datetime | None): 上一页末项创建时间；首页为 None。
            before_message_id (str | None): 上一页末项消息标识；首页为 None。

        Returns:
            list[MessageLogRecord]: 按 created_at、message_id 倒序排列的消息记录。
        """
        ...
