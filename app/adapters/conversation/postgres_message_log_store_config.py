"""Configuration for the PostgreSQL message log store."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.conversation.postgres_message_log_store_error import (
    PostgresMessageLogStoreError,
)
from app.config.env_loader import load_env_file, require_env


class PostgresMessageLogStoreConfig(BaseModel):
    """提供 message_log PostgreSQL Store 的类型化配置。"""

    dsn: str = Field(
        description="必填字段。message_log 所在 PostgreSQL 数据库连接字符串。",
    )
    schema_name: str = Field(
        default="public",
        min_length=1,
        description="message_log 表所在 PostgreSQL schema 名称。",
    )
    table_name: str = Field(
        default="message_log",
        min_length=1,
        description="保存 MessageLogRecord 的 PostgreSQL 表名。",
    )

    @classmethod
    def from_env(cls) -> "PostgresMessageLogStoreConfig":
        """从环境变量构造 message log Store 配置。

        Args:
            无显式业务参数。配置从 message log PostgreSQL 环境变量读取。

        Returns:
            PostgresMessageLogStoreConfig: 已完成环境变量解析的类型化配置。
        """

        load_env_file()
        dsn = require_env(
            "POSTGRES_MESSAGE_LOG_DSN",
            PostgresMessageLogStoreError,
            "POSTGRES_MESSAGE_LOG_DSN is required.",
        )
        return cls(
            dsn=dsn,
            schema_name=os.getenv(
                "POSTGRES_MESSAGE_LOG_SCHEMA",
                cls.model_fields["schema_name"].default,
            ),
            table_name=os.getenv(
                "POSTGRES_MESSAGE_LOG_TABLE",
                cls.model_fields["table_name"].default,
            ),
        )
