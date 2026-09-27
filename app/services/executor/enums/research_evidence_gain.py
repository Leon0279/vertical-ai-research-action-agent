"""Research iteration 证据增益枚举。"""

from enum import StrEnum


class ResearchEvidenceGain(StrEnum):
    """表示单轮 acquisition 与 processing 产生的有效证据增益。"""

    # 明显增益：新增证据直接且实质地推进了当前研究目标。
    MEANINGFUL_GAIN = "meaningful_gain"

    # 有限增益：新增证据相关但作用较小，未显著改变研究状态。
    LIMITED_GAIN = "limited_gain"

    # 无实质增益：材料重复、无关、不可用或没有形成新的有效证据。
    NO_MEANINGFUL_GAIN = "no_meaningful_gain"

    # 获取失败：acquisition 或 evidence processing 没有成功完成。
    FAILED_ACQUISITION = "failed_acquisition"
