"""Semantic relation result used by memory persistence."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import SemanticRelation


class SemanticResolutionResult(BaseModel):
    """确定性判断一个 memory candidate 与已有记录关系的结果。"""

    relation: SemanticRelation = Field(
        description=(
            "candidate 与已有 typed memory record 的关系。该字段只表达语义关系，"
            "不直接等同于最终 persistence action。"
        ),
    )
    matched_record_id: str | None = Field(
        default=None,
        description=(
            "本次语义关系所对应的唯一已有记录标识。relation 为 no_match 时必须为空；"
            "其它关系必须指向真正匹配的已有记录，供 persistence 精确执行去重、替换、"
            "supersede 或状态迁移。"
        ),
    )
    reason: str = Field(
        min_length=1,
        description=(
            "解释 resolver 如何得出当前关系的简短原因，供 persistence 生成 no-write 原因、"
            "记录日志和调试规则使用；该文本不参与持久化动作判断。"
        ),
    )

    @model_validator(mode="after")
    def validate_matched_record_id(self) -> "SemanticResolutionResult":
        """保证关系类型与匹配记录标识保持一致。"""

        if self.relation == SemanticRelation.NO_MATCH:
            if self.matched_record_id is not None:
                raise ValueError("no_match relation must not include matched_record_id")
            return self

        if not self.matched_record_id or not self.matched_record_id.strip():
            raise ValueError(
                f"{self.relation.value} relation requires matched_record_id"
            )
        return self
