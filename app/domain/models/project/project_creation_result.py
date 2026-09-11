"""Domain result for creating a project."""

from pydantic import BaseModel, Field


class ProjectCreationResult(BaseModel):
    """项目创建成功后的业务结果。"""

    project_id: str = Field(
        min_length=1,
        description=(
            "必填字段。服务端生成的稳定逻辑项目标识；后续 agent 请求可使用该值加载项目范围 memory。"
        ),
    )
