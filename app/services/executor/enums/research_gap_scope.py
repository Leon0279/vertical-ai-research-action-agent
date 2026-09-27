"""Research gap 所在层级枚举。"""

from enum import StrEnum


class ResearchGapScope(StrEnum):
    """表示一个研究缺口直接影响的任务层级或对象范围。"""

    # 缺口影响整体研究目标是否能够被回答。
    OBJECTIVE_LEVEL = "objective_level"

    # 缺口只影响规划阶段拆出的某个子问题。
    SUB_QUESTION_LEVEL = "sub_question_level"

    # 缺口影响多个对象之间能否进行完整、平衡的比较。
    COMPARISON_LEVEL = "comparison_level"

    # 缺口集中在某一个具体候选对象。
    CANDIDATE_LEVEL = "candidate_level"

    # 缺口集中在比较或评估中的某个维度。
    DIMENSION_LEVEL = "dimension_level"

    # 缺口直接影响某条 intermediate finding 是否成立。
    FINDING_LEVEL = "finding_level"

    # 缺口影响现有材料是否足以形成面向用户的推荐或决策。
    RECOMMENDATION_READINESS_LEVEL = "recommendation_readiness_level"
