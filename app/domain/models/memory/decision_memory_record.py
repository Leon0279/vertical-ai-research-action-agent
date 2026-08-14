"""Domain model for one decision_memory row."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DecisionMemoryRecord(BaseModel):
    """Typed decision memory record aligned with the LLD table schema."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(
        min_length=1,
        description="必填字段。一条 durable decision memory record 的主标识，用于版本关联与 supersession。",
    )
    user_id: str = Field(
        min_length=1,
        description="必填字段。该项目范围 decision memory 的用户归属边界，用于访问隔离。",
    )
    project_id: str = Field(
        min_length=1,
        description="必填字段。该 decision 所属的稳定逻辑 project 标识。",
    )
    decision_title: str | None = Field(
        default=None,
        description="可选字段。决策的简短标题；未命名时为 None。",
    )
    decision_question: str | None = Field(
        default=None,
        description="可选字段。该决策要解决的问题或取舍；未知时为 None。",
    )
    chosen_option: str | None = Field(
        default=None,
        description="可选字段。决策最终选择的方案；尚未确定或未记录时为 None。",
    )
    alternatives: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。形成决策时考虑过的备选方案。",
    )
    rationale: str | None = Field(
        default=None,
        description="可选字段。支撑该决策的主要理由、证据或判断依据。",
    )
    tradeoffs: list[str] = Field(
        default_factory=list,
        description="可选字段，默认空列表。该决策涉及的关键 trade-off。",
    )
    decision_state: str | None = Field(
        default=None,
        description=(
            "可选字段。decision 的业务状态，例如 proposed、accepted、reconsidering 或 rejected。"
        ),
    )
    record_status: str = Field(
        min_length=1,
        description=(
            "必填字段。该 memory record 的生命周期状态，例如 active、superseded、archived 或 pruned。"
        ),
    )
    impact_scope: str | None = Field(
        default=None,
        description="可选字段。该决策影响的项目、模块、用户或业务范围。",
    )
    confidence: float | None = Field(
        default=None,
        description="可选字段。当前 decision record 内容的可信度数值；未评估时为 None。",
    )
    decided_at: datetime | None = Field(
        default=None,
        description="可选字段。该决策形成时间；未知时为 None。",
    )
    supersedes_decision_id: str | None = Field(
        default=None,
        description="可选字段。被当前决策 supersede 的旧 decision record 标识。",
    )
    superseded_by_decision_id: str | None = Field(
        default=None,
        description="可选字段。已经 supersede 当前记录的新 decision record 标识。",
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
        description="可选字段。该 decision memory record 首次创建时间。",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="可选字段。该 decision memory record 最近更新时间。",
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
        description="可选字段，默认空列表。支撑该 decision record 的轻量来源句柄列表，不保存完整 SourceReference。",
    )
