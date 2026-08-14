"""Contract for session memory stores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import SessionMemory


@runtime_checkable
class SessionMemoryStoreProtocol(Protocol):
    """定义会话记忆存储的抽象交互契约。

Protocol for short-term session memory storage."""

    async def load(self, *, user_id: str, session_id: str | None) -> SessionMemory | None:
        """按用户和 session 边界读取短期会话记忆。

        Args:
            user_id (str): 所属用户标识，用于隔离 session memory。
            session_id (str | None): 需要读取的会话标识；为 None 时不应命中具体 session memory。

        Returns:
            SessionMemory | None: 当前会话的紧凑连续性记忆；不存在时返回 None。
        """

    async def save(self, memory: SessionMemory) -> None:
        """持久化短期会话连续性记忆。

        Args:
            memory (SessionMemory): 需要保存的会话摘要、当前推荐、行动项和开放问题等紧凑状态。

        Returns:
            None: 保存成功后无返回值；底层存储异常由实现向调用方抛出。
        """
