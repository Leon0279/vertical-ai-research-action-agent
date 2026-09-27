"""Research finding 变化枚举。"""

from enum import StrEnum


class ResearchFindingProgress(StrEnum):
    """表示本轮材料对 intermediate findings 稳定性的影响。"""

    # findings 得到充分补强，并由不稳定状态提升为稳定状态。
    IMPROVED_TO_STABLE = "improved_to_stable"

    # findings 有所改善，但仍保留会影响最终结论的重要不确定性。
    IMPROVED_BUT_NOT_STABLE = "improved_but_not_stable"

    # findings 的核心内容和成熟度没有发生实质变化。
    NO_MATERIAL_CHANGE = "no_material_change"

    # 新证据引入冲突或限制，使 findings 比本轮开始时更不确定。
    BECAME_LESS_CERTAIN = "became_less_certain"
