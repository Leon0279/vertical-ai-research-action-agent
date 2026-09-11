"""Error response schema for the project creation endpoint."""

from pydantic import BaseModel, Field


class CreateProjectErrorResponse(BaseModel):
    """表示项目创建请求未成功完成时的稳定错误响应。"""

    error_code: str = Field(
        min_length=1,
        description="必填字段。供客户端稳定判断错误类别的机器可读错误码。",
    )
    error_reason: str = Field(
        min_length=1,
        description="必填字段。可安全展示或记录的错误原因，不包含数据库连接或 SQL 细节。",
    )
