"""检索结果对当前研究目标的实际效用枚举。"""

from __future__ import annotations

from enum import StrEnum


class RetrievalResultUtility(StrEnum):
    """Research Executor 对单次检索路径实际推进价值的共享判断。

    它与 ``AcquisitionStatus`` 分别表达两个维度：后者描述 retrieval 是否成功返回
    材料，前者描述这些材料在完成 Evidence Processing 和本轮 outcome 判断后，是否
    真正推进了当前 coverage target。该枚举当前由 Research Executor 写入
    ``RecentRetrievalAttempt``，并由后续 iteration 的路径规避与 query 去重逻辑消费。
    """

    # 很有用：本轮证据直接解决或基本填补当前 coverage target 的核心缺口。
    HIGHLY_USEFUL = "highly_useful"

    # 较有用：本轮证据显著推进当前 coverage target，但尚未完全解决核心缺口。
    STRONGLY_USEFUL = "strongly_useful"

    # 有用：本轮证据与当前 coverage target 明确相关，并产生了实际增量。
    USEFUL = "useful"

    # 微弱有用：本轮证据只有有限、间接或不稳定的增量，不值得立即重复同一 family。
    WEAKLY_USEFUL = "weakly_useful"

    # 无用：未获得可用证据，或返回的证据无关、重复、不可用，
    # 未推进当前 coverage target。
    NOT_USEFUL = "not_useful"
