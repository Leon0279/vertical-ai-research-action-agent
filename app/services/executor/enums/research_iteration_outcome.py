"""Research iteration 最终控制结果枚举。"""

from enum import StrEnum


class ResearchIterationOutcome(StrEnum):
    """表示单轮研究结束后对 research loop 的控制决定。"""

    # 继续研究：当前仍有可推进的重要缺口，且预算与获取路径允许进入下一轮。
    CONTINUE = "continue"

    # 正常停止：研究目标已获得足够支撑，或继续研究的边际价值已经很低。
    STOP = "stop"

    # 降级结束：研究未充分完成，但因失败、路径耗尽或预算限制无法可靠继续。
    DEGRADE = "degrade"
