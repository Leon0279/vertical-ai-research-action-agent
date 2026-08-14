"""Domain model for one preference_policy_memory row."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PreferencePolicyMemoryRecord(BaseModel):
    """Typed preference/policy memory record aligned with the adjusted table schema."""

    model_config = ConfigDict(extra="forbid")

    policy_id: str = Field(
        min_length=1,
        description="必填字段。一条 durable preference 或 policy record 的主标识。",
    )
    user_id: str = Field(
        min_length=1,
        description="必填字段。该 policy record 的所属用户标识，用于用户级隔离。",
    )
    project_id: str | None = Field(
        default=None,
        description="可选字段。规则属于项目范围时关联的 project 标识；非项目规则时为 None。",
    )
    owner_scope_type: str = Field(
        min_length=1,
        description="必填字段。规则的拥有者 scope 层级，例如 global、user 或 project。",
    )
    owner_scope_value: str | None = Field(
        default=None,
        description="可选字段。进一步区分 owner scope 的值，例如 global 规则的系统 owner id。",
    )
    target_scope_type: str | None = Field(
        default=None,
        description="可选字段。规则作用目标的类型，例如 task_type 或 memory_type；不限制时为 None。",
    )
    target_scope_value: str | None = Field(
        default=None,
        description="可选字段。进一步限定规则作用位置的 target scope 值；不限制时为 None。",
    )
    policy_type: str = Field(
        min_length=1,
        description="必填字段。规则类别，例如 preference、constraint、format_rule 或 behavior_rule。",
    )
    policy_text: str = Field(
        min_length=1,
        description="必填字段。可跨 session 复用的规则文本或 policy 声明。",
    )
    conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="可选字段，默认空字典。进一步限制规则生效条件的 JSON-safe 条件集合。",
    )
    priority: int | None = Field(
        default=None,
        description="可选字段。规则冲突时的优先级数值；未设置时由调用方策略决定。",
    )
    enforcement_level: str | None = Field(
        default=None,
        description="可选字段。规则约束强度，例如 soft、default 或 strict。",
    )
    record_status: str = Field(
        min_length=1,
        description=(
            "必填字段。该 memory record 的生命周期状态，例如 active、superseded、archived 或 pruned。"
        ),
    )
    confidence: float | None = Field(
        default=None,
        description="可选字段。当前 preference/policy record 内容的可信度数值；未评估时为 None。",
    )
    supersedes_policy_id: str | None = Field(
        default=None,
        description="可选字段。被当前规则 supersede 的旧 policy record 标识。",
    )
    superseded_by_policy_id: str | None = Field(
        default=None,
        description="可选字段。已经 supersede 当前记录的新 policy record 标识。",
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
        description="可选字段。该 preference/policy record 首次创建时间。",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="可选字段。该 preference/policy record 最近更新时间。",
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
        description="可选字段，默认空列表。支撑该 policy record 的轻量来源句柄列表，不保存完整 SourceReference。",
    )
