"""Response schema for listing project identifiers."""

from pydantic import BaseModel, Field


class ListProjectIdsResponse(BaseModel):
    """表示指定用户当前所有项目标识的 API 响应。"""

    project_ids: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。该用户当前拥有 active Project Profile 的项目标识，"
            "按最近更新时间倒序排列。"
        ),
    )
