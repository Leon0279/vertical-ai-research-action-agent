"""Success response schema for the project creation endpoint."""

from pydantic import BaseModel, Field


class CreateProjectResponse(BaseModel):
    """表示项目创建成功后的 API 响应。"""

    project_id: str = Field(
        min_length=1,
        description="必填字段。新项目的稳定逻辑标识，可传给后续 agent run 请求。",
    )
