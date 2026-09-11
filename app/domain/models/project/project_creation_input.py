"""Domain input for creating a project."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


_ProjectConstraint = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]


class ProjectCreationInput(BaseModel):
    """创建项目及其首个 Project Profile 版本所需的业务输入。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_id: str = Field(
        min_length=1,
        max_length=200,
        description=(
            "必填字段。新项目所属的用户标识。当前项目尚未建立 user 表，因此只校验该值非空，"
            "不验证用户是否真实存在。"
        ),
    )
    project_name: str = Field(
        min_length=1,
        max_length=200,
        description="必填字段。项目名称；名称不是项目身份键，同一用户可以创建同名项目。",
    )
    project_description: str = Field(
        min_length=1,
        max_length=5000,
        description=(
            "必填字段。项目的基础背景描述；创建首个 Project Profile 时会映射到 project_background。"
        ),
    )
    project_goal: str | None = Field(
        default=None,
        min_length=1,
        max_length=2000,
        description="可选字段。项目希望长期达成的主要目标；尚未明确时为 None。",
    )
    domain: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="可选字段。项目所属的业务、技术或研究领域。",
    )
    current_stage: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="可选字段。项目创建时所处的阶段，例如探索、实施或验证。",
    )
    constraints: list[_ProjectConstraint] = Field(
        default_factory=list,
        max_length=20,
        description="可选字段，默认空列表。创建时已知且需要跨 session 保留的项目约束。",
    )
    important_context: str | None = Field(
        default=None,
        min_length=1,
        max_length=5000,
        description="可选字段。除基础项目描述外，未来运行仍应持续了解的重要上下文。",
    )
