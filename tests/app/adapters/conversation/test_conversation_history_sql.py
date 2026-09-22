"""Conversation history DDL contract tests."""

from pathlib import Path


_SQL_ROOT = Path(__file__).parents[4] / "docs" / "sql"


def test_conversation_history_tables_do_not_define_foreign_keys() -> None:
    sessions_sql = (_SQL_ROOT / "conversation_sessions.sql").read_text()
    messages_sql = (_SQL_ROOT / "message_log.sql").read_text()

    assert "FOREIGN KEY (" not in sessions_sql.upper()
    assert "FOREIGN KEY (" not in messages_sql.upper()
    assert "REFERENCES " not in sessions_sql.upper()
    assert "REFERENCES " not in messages_sql.upper()


def test_message_history_indexes_include_stable_sort_keys() -> None:
    messages_sql = (_SQL_ROOT / "message_log.sql").read_text()

    assert "session_id,\n        created_at DESC,\n        message_id DESC" in messages_sql
    assert "project_id,\n        created_at DESC,\n        message_id DESC" in messages_sql
