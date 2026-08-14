"""Domain model for one project_profile_memory row."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectProfileMemoryRecord(BaseModel):
    """Typed project profile memory record aligned with the LLD table schema."""

    model_config = ConfigDict(extra="forbid")

    project_profile_id: str = Field(
        min_length=1,
        description=(
            "必填字段。某一具体 project profile record 版本的标识，不等同于逻辑 project 本身。"
        ),
    )
    project_id: str = Field(
        min_length=1,
        description=(
            "必填字段。同一项目多个 project profile 版本共享的稳定逻辑 project 标识。"
        ),
    )
    user_id: str = Field(
        min_length=1,
        description="必填字段。该项目范围长期 memory 的用户归属边界，用于访问隔离。",
    )
    project_name: str | None = Field(
        default=None,
        description="可选字段。项目名称；未知或未命名时为 None。",
    )
    project_goal: str | None = Field(
        default=None,
        description="可选字段。项目长期目标或当前主要目标；未提炼时为 None。",
    )
    project_background: str | None = Field(
        default=None,
        description="可选字段。理解项目所需的背景摘要，不应保存完整原始项目材料。",
    )
    domain: str | None = Field(
        default=None,
        description="可选字段。项目所属业务、技术或研究领域。",
    )
    current_stage: str | None = Field(
        default=None,
        description="可选字段。项目当前所处阶段，例如探索、实施或验证。",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description=(
            "可选字段，默认空列表。跨 session 仍有持久价值的项目级约束。"
        ),
    )
    important_context: str | None = Field(
        default=None,
        description="可选字段。长期仍有助于理解项目的重要上下文摘要。",
    )
    record_status: str = Field(
        min_length=1,
        description=(
            "必填字段。该 memory record 的生命周期状态，例如 active、superseded、archived 或 pruned。"
        ),
    )
    confidence: float | None = Field(
        default=None,
        description="可选字段。当前 project profile 内容的可信度数值；未评估时为 None。",
    )
    supersedes_profile_id: str | None = Field(
        default=None,
        description="可选字段。被当前 profile replace 的旧 project profile record 标识。",
    )
    superseded_by_profile_id: str | None = Field(
        default=None,
        description="可选字段。已经 replace 当前记录的新 project profile record 标识。",
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
        description="可选字段。该 project profile record 首次创建时间。",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="可选字段。该 project profile record 最近更新时间。",
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
        description="可选字段，默认空列表。支撑该 project profile record 的轻量来源句柄列表，不保存完整 SourceReference。",
    )
