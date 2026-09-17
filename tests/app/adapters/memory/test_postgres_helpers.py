"""Tests for private PostgreSQL memory adapter plumbing."""

from app.adapters.memory._postgres import postgres_table_ref


def test_postgres_table_reference() -> None:
    assert postgres_table_ref("public", "action_memory") == "public.action_memory"
