"""Research finding 成熟度枚举。"""

from enum import StrEnum


class ResearchFindingMaturity(StrEnum):
    """表示当前 intermediate findings 的稳定成熟程度。"""

    # 暂定：发现主要来自初步信号，后续材料很可能改变其内容。
    TENTATIVE = "tentative"

    # 部分稳定：核心方向已有支撑，但仍存在会影响表述或边界的重要缺口。
    PARTIALLY_STABLE = "partially_stable"

    # 稳定：核心发现已经获得充分、一致的证据支撑。
    STABLE = "stable"

    # 受阻：存在关键冲突或缺口，当前材料无法推动发现继续成熟。
    BLOCKED = "blocked"
