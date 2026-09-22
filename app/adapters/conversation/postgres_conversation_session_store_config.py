"""Configuration for the PostgreSQL conversation session store."""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from app.adapters.conversation.postgres_conversation_session_store_error import (
    PostgresConversationSessionStoreError,
)
from app.config.env_loader import load_env_file, require_env


class PostgresConversationSessionStoreConfig(BaseModel):
    """提供 conversation_sessions PostgreSQL Store 的类型化配置。"""

    dsn: str = Field(
        description="必填字段。conversation_sessions 所在 PostgreSQL 数据库连接字符串。",
    )
    schema_name: str = Field(
        default="public",
        min_length=1,
        description="conversation_sessions 表所在 PostgreSQL schema 名称。",
    )
    table_name: str = Field(
        default="conversation_sessions",
        min_length=1,
        description="保存 ConversationSessionRecord 的 PostgreSQL 表名。",
    )

    @classmethod
    def from_env(cls) -> "PostgresConversationSessionStoreConfig":
        """从环境变量构造 conversation session Store 配置。

        Args:
            无显式业务参数。配置从 conversation session PostgreSQL 环境变量读取。

        Returns:
            PostgresConversationSessionStoreConfig: 已完成环境变量解析的类型化配置。
        """

        load_env_file()
        dsn = require_env(
            "POSTGRES_CONVERSATION_SESSION_DSN",
            PostgresConversationSessionStoreError,
            "POSTGRES_CONVERSATION_SESSION_DSN is required.",
        )
        return cls(
            dsn=dsn,
            schema_name=os.getenv(
                "POSTGRES_CONVERSATION_SESSION_SCHEMA",
                cls.model_fields["schema_name"].default,
            ),
            table_name=os.getenv(
                "POSTGRES_CONVERSATION_SESSION_TABLE",
                cls.model_fields["table_name"].default,
            ),
        )
