"""Research Executor 单轮推进模式枚举。"""

from enum import StrEnum


class ResearchActionMode(StrEnum):
    """表示 Research Executor 为当前 iteration 选择的高层推进方式。"""

    # 不获取新材料，只利用已有证据和上下文继续整理或收敛研究状态。
    REFINE_FROM_EXISTING_STATE = "refine_from_existing_state"

    # 优先从长期 Research Knowledge Memory 中召回已有研究材料。
    MEMORY_BACKED_ACQUISITION = "memory_backed_acquisition"

    # 从文档、论文或网页等外部来源获取新的候选材料。
    EXTERNAL_ACQUISITION = "external_acquisition"
