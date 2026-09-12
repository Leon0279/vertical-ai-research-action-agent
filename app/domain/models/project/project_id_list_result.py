"""Domain result for listing one user's project identifiers."""

from pydantic import BaseModel, Field


class ProjectIdListResult(BaseModel):
    """表示按用户查询当前有效项目后得到的业务结果。"""

    project_ids: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。指定用户当前拥有 active Project Profile 的稳定项目标识，"
            "按项目档案最近更新时间倒序排列。"
        ),
    )
