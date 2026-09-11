"""Request schema for the project creation endpoint."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


_ProjectConstraint = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]


class CreateProjectRequest(BaseModel):
    """表示创建一个项目及其初始项目档案的 API 请求。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "必填字段。新项目所属用户的标识；当前尚无 user 表，因此只校验非空，不验证用户是否存在。"
        ),
    )
    project_name: str = Field(
        min_length=1,
        max_length=200,
        description="必填字段。项目名称；同一用户可以创建名称相同但 project_id 不同的项目。",
    )
    project_description: str = Field(
        min_length=1,
        max_length=5000,
        description="必填字段。项目的基础背景描述，将写入初始 Project Profile。",
    )
    project_goal: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
        description="可选字段。项目希望长期达成的主要目标。",
    )
    domain: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="可选字段。项目所属业务、技术或研究领域。",
    )
    current_stage: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="可选字段。项目创建时所处阶段。",
    )
    constraints: list[_ProjectConstraint] = Field(
        default_factory=list,
        max_length=20,
        description="可选字段，默认空列表。需要跨 session 保留的项目约束，最多 20 条。",
    )
    important_context: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
        description="可选字段。未来运行仍需持续了解的重要项目上下文。",
    )
