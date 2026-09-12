"""Response schema for current project details."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectDetailsResponse(BaseModel):
    """表示指定项目当前业务信息的 API 响应。"""

    project_id: str = Field(
        min_length=1,
        description="必填字段。跨 Project Profile 版本保持稳定的逻辑项目标识。",
    )
    project_name: str | None = Field(default=None, description="可选字段。项目名称。")
    project_description: str | None = Field(
        default=None,
        description="可选字段。当前项目档案中的项目背景描述。",
    )
    project_goal: str | None = Field(default=None, description="可选字段。项目目标。")
    domain: str | None = Field(default=None, description="可选字段。项目所属领域。")
    current_stage: str | None = Field(
        default=None,
        description="可选字段。项目当前阶段。",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。当前有效的项目约束。",
    )
    important_context: str | None = Field(
        default=None,
        description="可选字段。继续理解和推进项目所需的重要上下文摘要。",
    )
    profile_created_at: datetime | None = Field(
        default=None,
        description="可选字段。当前 active Project Profile 版本的创建时间。",
    )
    profile_updated_at: datetime | None = Field(
        default=None,
        description="可选字段。当前 active Project Profile 版本最近更新时间。",
    )
