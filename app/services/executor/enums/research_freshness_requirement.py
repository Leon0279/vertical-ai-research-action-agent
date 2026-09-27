"""Research evidence 新鲜度要求枚举。"""

from enum import StrEnum


class ResearchFreshnessRequirement(StrEnum):
    """表示下一项证据对发布时间或当前有效性的要求。"""

    # 普通要求：内容正确和相关即可，不强制近期发布。
    NORMAL = "normal"

    # 优先新鲜：近期材料更好，但高质量历史材料仍可接受。
    FRESH_PREFERRED = "fresh_preferred"

    # 必须新鲜：问题具有明显时效性，陈旧材料不能满足 evidence need。
    FRESH_REQUIRED = "fresh_required"

    # 无新鲜度要求：通常与无需新增证据的 no-op need 配合使用。
    NONE = "none"
