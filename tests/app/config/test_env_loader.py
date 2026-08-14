"""Environment loader tests."""

from __future__ import annotations

import os

from app.config import env_loader


def test_env_loader_reads_temp_env_without_overriding_existing_values(
    monkeypatch,
    tmp_path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "ZHIPU_API_KEY=loaded-key",
                "REDIS_SESSION_MEMORY_URL=redis://loaded.example/0",
                "QUOTED_VALUE='hello world'",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("VAA_SKIP_DOTENV", raising=False)
    monkeypatch.setenv("VAA_ENV_FILE", str(env_file))
    monkeypatch.setenv("ZHIPU_API_KEY", "existing-key")
    monkeypatch.delenv("REDIS_SESSION_MEMORY_URL", raising=False)
    monkeypatch.delenv("QUOTED_VALUE", raising=False)
    monkeypatch.setattr(env_loader, "_LOADED", False)

    env_loader.load_env_file()

    assert os.environ["ZHIPU_API_KEY"] == "existing-key"
    assert os.environ["REDIS_SESSION_MEMORY_URL"] == "redis://loaded.example/0"
    assert os.environ["QUOTED_VALUE"] == "hello world"


def test_env_loader_can_be_skipped(monkeypatch, tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("REDIS_SESSION_MEMORY_URL=redis://loaded.example/0", encoding="utf-8")

    monkeypatch.setenv("VAA_SKIP_DOTENV", "1")
    monkeypatch.setenv("VAA_ENV_FILE", str(env_file))
    monkeypatch.delenv("REDIS_SESSION_MEMORY_URL", raising=False)
    monkeypatch.setattr(env_loader, "_LOADED", False)

    env_loader.load_env_file()

    assert "REDIS_SESSION_MEMORY_URL" not in os.environ
