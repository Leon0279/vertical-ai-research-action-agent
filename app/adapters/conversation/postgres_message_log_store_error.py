"""Errors raised by the PostgreSQL message log store."""


class PostgresMessageLogStoreError(Exception):
    """表示 PostgreSQL message log 读取、写入或配置失败。"""
