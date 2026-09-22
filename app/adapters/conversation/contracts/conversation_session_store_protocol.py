"""Contract for persistent conversation session stores."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.domain.enums import ConversationSessionStatus
from app.domain.models import ConversationSessionRecord


@runtime_checkable
class ConversationSessionStoreProtocol(Protocol):
    """定义持久化 conversation session 元数据的存储契约。"""

    async def ensure_session(
        self,
        session: ConversationSessionRecord,
    ) -> ConversationSessionRecord:
        """确保指定会话存在，并拒绝复用不同用户或项目作用域的会话标识。

        Args:
            session (ConversationSessionRecord): 待创建或确认存在的完整会话记录。

        Returns:
            ConversationSessionRecord: 新创建的记录，或作用域一致时已存在的记录。
        """
        ...

    async def load_session(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> ConversationSessionRecord | None:
        """读取指定用户拥有的一条持久化会话记录。

        Args:
            user_id (str): 会话所属用户标识，用于隔离读取范围。
            session_id (str): 需要读取的稳定会话标识。

        Returns:
            ConversationSessionRecord | None: 匹配记录；不存在或不属于该用户时返回 None。
        """
        ...

    async def list_sessions(
        self,
        *,
        user_id: str,
        project_id: str | None,
        session_statuses: list[ConversationSessionStatus],
        limit: int,
        before_updated_at: datetime | None = None,
        before_session_id: str | None = None,
    ) -> list[ConversationSessionRecord]:
        """按更新时间倒序读取一批用户会话。

        Args:
            user_id (str): 会话所属用户标识，用于隔离读取范围。
            project_id (str | None): 可选项目过滤；None 表示读取该用户全部项目范围。
            session_statuses (list[ConversationSessionStatus]): 允许返回的会话状态集合。
            limit (int): 内部最大读取记录数，取值范围为 1 到 101；101 用于公开 100 条分页的 lookahead。
            before_updated_at (datetime | None): 上一页末项更新时间；首页为 None。
            before_session_id (str | None): 上一页末项会话标识；首页为 None。

        Returns:
            list[ConversationSessionRecord]: 按 updated_at、session_id 倒序排列的会话记录。
        """
        ...

    async def record_message_activity(
        self,
        *,
        user_id: str,
        session_id: str,
        message_created_at: datetime,
    ) -> None:
        """记录一条消息对会话最近活跃时间的影响。

        Args:
            user_id (str): 会话所属用户标识，用于隔离更新范围。
            session_id (str): 需要更新的稳定会话标识。
            message_created_at (datetime): 已持久化消息的创建时间。

        Returns:
            None: 更新成功后无返回值；会话不存在或存储失败时抛出异常。
        """
        ...
