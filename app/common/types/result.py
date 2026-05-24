"""Minimal result wrapper type."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class Result(Generic[T]):
    """Simple operation result wrapper."""

    ok: bool
    value: T | None = None
    error: str | None = None

