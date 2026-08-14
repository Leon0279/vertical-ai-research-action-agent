"""Domain model for one action_memory row."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ActionMemoryRecord(BaseModel):
    """表示行动记忆的持久化记录。

Typed action memory record aligned with the LLD table schema."""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(
        min_length=1,
        description="必填字段。一条 durable action memory record 的主标识，用于更新、状态迁移和关联。",
    )
    user_id: str = Field(
        min_length=1,
        description="必填字段。该项目范围 action memory 的用户归属边界，用于访问隔离。",
    )
    project_id: str = Field(
        min_length=1,
        description="必填字段。该 action 所属的稳定逻辑 project 标识。",
    )
    parent_decision_id: str | None = Field(
        default=None,
        description="可选字段。该 action 派生自的上游 decision record 标识；没有关联决策时为 None。",
    )
    action_title: str | None = Field(
        default=None,
        description="可选字段。行动项的简短标题；没有标题时为 None。",
    )
    action_description: str | None = Field(
        default=None,
        description="可选字段。行动项的详细执行描述、范围或预期产出；没有说明时为 None。",
    )
    action_status: str = Field(
        min_length=1,
        description=(
            "必填字段。action 的业务状态，例如 todo、in_progress、blocked、done 或 cancelled。"
        ),
    )
    priority: str | None = Field(
        default=None,
        description="可选字段。行动项优先级，用于排序和执行安排。",
    )
    owner: str | None = Field(
        default=None,
        description="可选字段。负责该行动项的 owner；未指定时为 None。",
    )
    due_at: datetime | None = Field(
        default=None,
        description="可选字段。行动项的截止时间；未设置时为 None。",
    )
    blocking_reason: str | None = Field(
        default=None,
        description="可选字段。行动项当前受阻的原因；非 blocked 状态或未知时为 None。",
    )
    result_summary: str | None = Field(
        default=None,
        description="可选字段。行动完成后的结果摘要；尚未完成或未记录结果时为 None。",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="可选字段。行动完成的时间；尚未完成或未知时为 None。",
    )
    record_status: str = Field(
        min_length=1,
        description=(
            "必填字段。该 memory record 的生命周期状态，例如 active、archived 或 pruned。"
        ),
    )
    confidence: float | None = Field(
        default=None,
        description="可选字段。当前 action record 内容的可信度数值；未评估时为 None。",
    )
    embedding_text: str | None = Field(
        default=None,
        description=(
            "可选字段。用于同类型语义相似度解析的 embedding 输入文本。"
        ),
    )
    embedding_model: str | None = Field(
        default=None,
        description="可选字段。生成关联 embedding 表示时使用的模型名称。",
    )
    embedding_version: str | None = Field(
        default=None,
        description="可选字段。embedding 模型或生成配置的版本标识。",
    )
    created_at: datetime | None = Field(
        default=None,
        description="可选字段。该 action memory record 首次创建时间。",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="可选字段。该 action memory record 最近更新时间。",
    )
    derived_from_session_id: str | None = Field(
        default=None,
        description="可选字段。提炼出该记录的来源 session 标识；无 session 来源时为 None。",
    )
    derived_from_run_id: str | None = Field(
        default=None,
        description="可选字段。提炼出该记录的来源 run 标识；无 run 来源时为 None。",
    )
    source_refs: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。支撑该 action record 的轻量来源句柄列表，不保存完整 SourceReference。",
    )
