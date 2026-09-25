"""Context Memory Loader Stage 的显式输入模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContextMemoryLoaderStageInput(BaseModel):
    """Context Memory Loader 执行检索与筛选时实际消费的输入子集。"""

    user_id: str = Field(
        min_length=1,
        description="必填字段。当前 run 的用户标识，用于隔离该用户可访问的 session 和长期记忆。",
    )
    session_id: str = Field(
        min_length=1,
        description="必填字段。当前 run 的会话标识，用于读取对应的短期 Session Memory。",
    )
    project_scope_id: str | None = Field(
        default=None,
        description="可选字段。当前 run 的项目范围标识；为空时跳过 project-scoped structured memory 查询。",
    )
    original_query: str = Field(
        min_length=1,
        description="必填字段。用户原始问题，作为 research knowledge recall query 的兜底语义来源。",
    )
    task_type: str | None = Field(
        default=None,
        description="可选字段。Task Interpretation 识别的任务类型，用于选择适用的 policy 和 research knowledge。",
    )
    user_goal: str | None = Field(
        default=None,
        description="可选字段。当前用户目标摘要，优先用于构造 research knowledge recall query。",
    )
    task_framing: str | None = Field(
        default=None,
        description="可选字段。当前任务 framing，用于补充 research knowledge recall query 的执行语境。",
    )
