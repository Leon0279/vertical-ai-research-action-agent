"""Research coverage target 类型枚举。"""

from enum import StrEnum


class ResearchCoverageTargetType(StrEnum):
    """表示 evidence coverage map 中受控目标的来源层级。"""

    # 整体研究目标，对应当前 Research Stage 的 objective。
    OBJECTIVE = "objective"

    # 规划阶段拆出的独立子问题。
    SUB_QUESTION = "sub_question"

    # comparison 任务中需要分别覆盖的候选对象。
    COMPARISON_CANDIDATE = "comparison_candidate"
