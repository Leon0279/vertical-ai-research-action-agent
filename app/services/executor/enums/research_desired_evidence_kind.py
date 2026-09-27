"""Research 期望证据类型枚举。"""

from enum import StrEnum


class ResearchDesiredEvidenceKind(StrEnum):
    """表示 Research Executor 希望下一轮获取的证据语义形态。"""

    # 能直接回答目标事实或验证关键命题的一手事实证据。
    DIRECT_FACT = "direct_fact"

    # 比现有材料更权威、更直接或更充分的支持性证据。
    STRONGER_SUPPORTING_EVIDENCE = "stronger_supporting_evidence"

    # 能消除歧义、限定含义或区分多种解释的证据。
    DISAMBIGUATING_EVIDENCE = "disambiguating_evidence"

    # 能对多个候选对象或维度进行同口径比较的证据。
    COMPARISON_EVIDENCE = "comparison_evidence"

    # 能反映当前时间点最新状态、版本或变化的证据。
    FRESH_STATUS_EVIDENCE = "fresh_status_evidence"

    # 能支撑选择、推荐、取舍或执行行动的证据。
    DECISION_SUPPORTING_EVIDENCE = "decision_supporting_evidence"

    # 当前不需要获取任何新增证据。
    NONE = "none"
