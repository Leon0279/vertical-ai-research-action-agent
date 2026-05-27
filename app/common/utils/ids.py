"""ID utility helpers."""

from uuid import uuid4


def generate_trace_id() -> str:
    """Generate a request trace id."""

    return f"trace-{uuid4().hex}"


def generate_session_id() -> str:
    """Generate a session id."""

    return f"session-{uuid4().hex}"
