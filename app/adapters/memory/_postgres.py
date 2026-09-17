"""Private PostgreSQL adapter plumbing shared by typed memory stores."""

def postgres_table_ref(schema_name: str, table_name: str) -> str:
    """构造当前 memory adapter 使用的 schema-qualified 表名。"""

    return f"{schema_name}.{table_name}"
