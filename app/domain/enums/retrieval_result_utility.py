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

    USEFUL = "useful"
    WEAKLY_USEFUL = "weakly_useful"
    NOT_USEFUL = "not_useful"
