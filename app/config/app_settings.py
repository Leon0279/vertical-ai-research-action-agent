"""Runtime settings model for the app."""

from pydantic import BaseModel, Field

from app.config.constants import (
    API_TITLE,
    API_VERSION,
    DEFAULT_MAX_RESEARCH_ITERATIONS,
    DEFAULT_MAX_TOOL_CALLS,
)


class AppSettings(BaseModel):
    """集中管理应用的运行时配置。

Simple typed settings without external env dependency."""

    api_title: str = Field(
        default=API_TITLE,
        description="对外 API 文档和服务标识使用的标题。",
    )
    api_version: str = Field(
        default=API_VERSION,
        description="当前 API 对外声明的版本号。",
    )
    max_research_iterations: int = Field(
        default=DEFAULT_MAX_RESEARCH_ITERATIONS,
        description="单个请求允许的默认 research iteration 上限，用于防止研究循环无界执行。",
    )
    max_tool_calls: int = Field(
        default=DEFAULT_MAX_TOOL_CALLS,
        description="单个请求允许的默认工具调用上限，用于控制资源消耗和恢复重试范围。",
    )
