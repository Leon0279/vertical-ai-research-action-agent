"""Errors raised by the Redis session memory adapter."""


class RedisSessionMemoryStoreError(Exception):
    """表示Redis会话记忆存储执行过程中发生的错误。

Redis session memory adapter configuration or setup error."""
