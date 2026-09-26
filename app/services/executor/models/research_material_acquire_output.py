"""ResearchMaterialAcquirer.acquire 的强类型输出边界。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import (
    NormalizedRetrievalItem,
    ToolExecutionLayerRequest,
    ToolExecutionLayerResult,
)


class ResearchMaterialAcquireOutput(BaseModel):
    """TEL 调用成功后交还给 Research Executor 的完整 acquisition 结果。"""

    model_config = ConfigDict(extra="forbid")

    tool_execution_request: ToolExecutionLayerRequest = Field(
        description=(
            "必填字段。本轮实际发送给 Tool Execution Layer 的强类型请求。"
        ),
    )
    tool_execution_result: ToolExecutionLayerResult = Field(
        description="必填字段。Tool Execution Layer 返回的稳定强类型结果。",
    )
    candidate_materials: list[NormalizedRetrievalItem] = Field(
        description="必填字段。从 TEL result 投影出的本轮候选材料列表。",
    )
