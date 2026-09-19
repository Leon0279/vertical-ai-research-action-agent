"""Strongly typed Action Memory business statuses."""

from typing import Literal, TypeAlias


ActionMemoryStatus: TypeAlias = Literal[
    "todo",
    "in_progress",
    "blocked",
    "done",
    "cancelled",
]
