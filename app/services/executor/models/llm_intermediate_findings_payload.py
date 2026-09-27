"""LLM 中间发现精炼的 service-private 输出模型。"""

from pydantic import BaseModel, ConfigDict, Field


class LLMIntermediateFindingsPayload(BaseModel):
    """表示大语言模型对中间发现的完整替换结果。

    Strict LLM output payload for full intermediate finding replacement.
    """

    model_config = ConfigDict(extra="forbid")

    intermediate_findings: list[str] = Field(
        description=(
            "必填字段。LLM 返回的全量更新后中间发现列表，"
            "而非仅本轮增量。例如：[\"官方文档确认方案 A 支持并发处理，"
            "但尚无材料证明其峰值吞吐量。\"]。"
        ),
    )
    finding_caveats: list[str] = Field(
        description=(
            "必填字段。与当前中间发现对应的全量限制、风险或"
            "不确定性说明列表。"
            "例如：[\"当前判断缺少独立基准测试数据支持。\"]。"
        ),
    )
