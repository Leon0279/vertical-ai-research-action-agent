"""Research gap 严重程度枚举。"""

from enum import StrEnum


class ResearchGapSeverity(StrEnum):
    """表示研究缺口对完成当前目标的影响程度。"""

    # 阻塞：不解决该缺口就无法可靠回答核心目标。
    BLOCKING = "blocking"

    # 重要：会显著影响结论质量，但不一定完全阻止形成部分结果。
    IMPORTANT = "important"

    # 可选：补齐后可提升完整性，但不影响核心结论成立。
    OPTIONAL = "optional"

    # 无严重程度：当前没有实际研究缺口。
    NONE = "none"
