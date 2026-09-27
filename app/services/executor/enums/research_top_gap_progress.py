"""Research top gap 推进程度枚举。"""

from enum import StrEnum


class ResearchTopGapProgress(StrEnum):
    """表示当前 iteration 对开始时 top gap 的实际推进程度。"""

    # 已解决：本轮材料已经消除 top gap 的核心不确定性。
    RESOLVED = "resolved"

    # 部分推进：获得了有效增量，但 top gap 仍未完全解决。
    PARTIALLY_ADVANCED = "partially_advanced"

    # 未推进：本轮没有为 top gap 带来实质增量。
    NOT_ADVANCED = "not_advanced"

    # 退化：新材料引入冲突或削弱了原有判断的可靠性。
    REGRESSED = "regressed"
