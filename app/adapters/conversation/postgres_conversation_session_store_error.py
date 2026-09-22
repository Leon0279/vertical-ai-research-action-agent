"""Errors raised by the PostgreSQL conversation session store."""


class PostgresConversationSessionStoreError(Exception):
    """表示 PostgreSQL conversation session 读取、写入或配置失败。"""
