"""ID utility helpers."""

from uuid import uuid4


def generate_trace_id() -> str:
    """Generate a request trace id."""

    return f"trace-{uuid4().hex}"


def generate_session_id() -> str:
    """Generate a session id."""

    return f"session-{uuid4().hex}"


def generate_project_id() -> str:
    """生成跨 Project Profile 版本保持稳定的逻辑项目标识。"""

    return f"project-{uuid4().hex}"


def generate_project_profile_id() -> str:
    """生成单个 Project Profile 持久化版本的记录标识。"""

    return f"project-profile-{uuid4().hex}"
