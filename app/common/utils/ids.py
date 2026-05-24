"""ID utility helpers."""

from uuid import uuid4


def generate_trace_id() -> str:
    """Generate a request trace id."""

    return f"trace-{uuid4().hex}"

