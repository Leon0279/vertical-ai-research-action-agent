"""Semantic relation enums used by memory resolution."""

from enum import StrEnum


class SemanticRelation(StrEnum):
    """表示 memory candidate 与一条已有记忆记录之间的语义关系。

    该枚举只描述 candidate 是否匹配已有记录以及匹配后的变化性质，不直接
    表示 create、replace、supersede 等最终持久化动作。
    """

    # 没有找到与 candidate 表示同一逻辑对象的已有记录，通常可按新对象处理。
    NO_MATCH = "no_match"

    # 找到了同一逻辑对象，且双方核心语义一致，不需要重复持久化。
    DUPLICATE = "duplicate"

    # 找到了同一逻辑对象，但内容发生了可按新版本处理的普通变化。
    CHANGED = "changed"

    # 找到了同一逻辑对象，主要变化是 action 等状态型记录的生命周期状态推进。
    STATE_TRANSITION = "state_transition"

    # 找到了同一逻辑对象，但关键事实互相矛盾，无法直接视为普通内容更新。
    CONFLICT = "conflict"
