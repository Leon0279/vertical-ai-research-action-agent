"""ResearchMaterialAcquirer.acquire 的强类型输入边界。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import RecentRetrievalAttempt
from app.services.executor.models.research_action_request import ResearchActionRequest


class ResearchMaterialAcquireInput(BaseModel):
    """单次 Research Material Acquisition 实际消费的只读状态快照。"""

    model_config = ConfigDict(extra="forbid")

    original_query: str = Field(
        min_length=1,
        description=(
            "必填字段。用户原始问题，作为 TEL target problem 的最终兜底。"
        ),
    )
    user_goal: str | None = Field(
        description=(
            "可空字段。当前用户目标摘要，可作为 TEL target problem 的语义来源。"
        ),
    )
    task_framing: str | None = Field(
        description="可空字段。当前任务 framing，将原样投影到 TEL request。",
    )
    owner_user_id: str | None = Field(
        description="可空字段。memory-backed acquisition 使用的用户所有权边界。",
    )
    project_scope_id: str | None = Field(
        description="可空字段。memory-backed acquisition 使用的项目范围边界。",
    )
    latency_budget_ms: int | None = Field(
        description="可空字段。传递给 TEL 的超时预算，单位为毫秒。",
    )
    iteration_index: int = Field(
        ge=1,
        description="必填字段。当前 Research Executor iteration 从 1 开始的序号。",
    )
    action_request: ResearchActionRequest = Field(
        description="必填字段。ResearchActionDecider 生成的内部 acquisition 请求。",
    )
    coverage_target_key: str = Field(
        min_length=1,
        description="必填字段。本轮 acquisition 所服务的稳定 coverage target key。",
    )
    recent_retrieval_attempts: list[RecentRetrievalAttempt] = Field(
        description=(
            "必填字段。本 Research Stage 内可用于 TEL 避免低价值重复检索的近期历史。"
        ),
    )
