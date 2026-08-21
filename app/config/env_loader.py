"""Small, idempotent loader for local .env configuration."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

_LOADED = False


def require_env(name: str, error_factory: Callable[[str], Exception], message: str) -> str:
    """读取必填环境变量；空白值缺失时保留调用方的异常类型和文案。"""

    value = os.getenv(name, "").strip()
    if value:
        return value
    raise error_factory(message)


def load_env_file() -> None:
    """Load local .env values without overriding already exported variables."""

    global _LOADED
    if _LOADED or os.getenv("VAA_SKIP_DOTENV"):
        return
    _LOADED = True

    env_path = _env_path()
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv
    except ImportError:
        _load_env_file_without_dotenv(env_path)
        return

    load_dotenv(dotenv_path=env_path, override=False)


def _env_path() -> Path:
    override = os.getenv("VAA_ENV_FILE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / ".env"


def _load_env_file_without_dotenv(env_path: Path) -> None:
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = _clean_env_value(value)


def _clean_env_value(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        return cleaned[1:-1]
    return cleaned
