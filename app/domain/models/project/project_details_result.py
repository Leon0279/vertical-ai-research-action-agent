"""Domain result for retrieving current project details."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectDetailsResult(BaseModel):
    """表示一个项目当前 active Project Profile 对外提供的业务信息。"""

    project_id: str = Field(
        min_length=1,
        description="必填字段。跨 Project Profile 版本保持稳定的逻辑项目标识。",
    )
    project_name: str | None = Field(
        default=None,
        description="可选字段。项目名称；当前档案没有名称时为 None。",
    )
    project_description: str | None = Field(
        default=None,
        description=(
            "可选字段。项目的背景描述，由当前 Project Profile 的 project_background 映射得到。"
        ),
    )
    project_goal: str | None = Field(
        default=None,
        description="可选字段。项目当前记录的长期目标或主要目标。",
    )
    domain: str | None = Field(
        default=None,
        description="可选字段。项目所属的业务、技术或研究领域。",
    )
    current_stage: str | None = Field(
        default=None,
        description="可选字段。项目当前所处阶段，例如探索、实施或验证。",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。当前项目档案中仍然有效的项目级约束。",
    )
    important_context: str | None = Field(
        default=None,
        description="可选字段。理解和继续推进项目时应保留的重要上下文摘要。",
    )
    profile_created_at: datetime | None = Field(
        default=None,
        description=(
            "可选字段。当前 active Project Profile 版本的创建时间，不表示逻辑项目首次创建时间。"
        ),
    )
    profile_updated_at: datetime | None = Field(
        default=None,
        description="可选字段。当前 active Project Profile 版本最近一次更新时间。",
    )
