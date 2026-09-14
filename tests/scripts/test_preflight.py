"""Local Docker preflight script tests."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_PREFLIGHT_SCRIPT = _REPOSITORY_ROOT / "scripts" / "preflight.sh"


def _write_fake_commands(directory: Path) -> None:
    docker = directory / "docker"
    docker.write_text(
        """#!/bin/sh
if [ \"$1\" = \"container\" ] && [ \"$2\" = \"inspect\" ]; then
    [ \"${FAKE_LEGACY_CONTAINER:-0}\" = \"1\" ] && exit 0
    exit 1
fi
exit 0
""",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    lsof = directory / "lsof"
    lsof.write_text(
        """#!/bin/sh
if [ -n \"${FAKE_LISTENER_PID:-}\" ]; then
    printf '%s\\n' \"$FAKE_LISTENER_PID\"
    exit 0
fi
exit 1
""",
        encoding="utf-8",
    )
    lsof.chmod(0o755)


def _valid_env() -> str:
    return """ZHIPU_API_KEY=zhipu-real-value
TAVILY_API_KEY=tavily-real-value
ARXIV_PAPER_SEARCH_CLIENT_IDENTITY=contact:developer@domain.test
ARXIV_PAPER_CONTENT_FETCH_CLIENT_IDENTITY=contact:developer@domain.test
API_PORT=18000
POSTGRES_PORT=15432
REDIS_PORT=16379
"""


def _run_preflight(tmp_path: Path, env_text: str, **extra_env: str):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_commands(fake_bin)
    env_file = tmp_path / ".env"
    env_file.write_text(env_text, encoding="utf-8")
    process_env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "VAA_ENV_FILE": str(env_file),
        **extra_env,
    }
    return subprocess.run(
        ["/bin/sh", str(_PREFLIGHT_SCRIPT)],
        cwd=_REPOSITORY_ROOT,
        env=process_env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_preflight_accepts_real_configuration(tmp_path) -> None:
    result = _run_preflight(tmp_path, _valid_env())

    assert result.returncode == 0
    assert result.stdout == "Preflight checks passed.\n"


def test_preflight_rejects_placeholder_without_printing_other_secrets(tmp_path) -> None:
    secret = "zhipu-secret-that-must-not-leak"
    result = _run_preflight(
        tmp_path,
        _valid_env()
        .replace("zhipu-real-value", secret)
        .replace("tavily-real-value", "replace-with-your-tavily-api-key"),
    )

    assert result.returncode == 1
    assert "TAVILY_API_KEY" in result.stderr
    assert secret not in result.stderr
    assert "replace-with-your-tavily-api-key" not in result.stderr


def test_preflight_rejects_legacy_container(tmp_path) -> None:
    result = _run_preflight(
        tmp_path,
        _valid_env(),
        FAKE_LEGACY_CONTAINER="1",
    )

    assert result.returncode == 1
    assert "make adopt-local-data CONFIRM_ADOPT=YES" in result.stderr


def test_preflight_allows_expected_legacy_container_during_adoption(tmp_path) -> None:
    result = _run_preflight(
        tmp_path,
        _valid_env(),
        FAKE_LEGACY_CONTAINER="1",
        ALLOW_LEGACY_CONTAINERS="1",
    )

    assert result.returncode == 0


def test_preflight_rejects_non_docker_port_listener(tmp_path) -> None:
    result = _run_preflight(
        tmp_path,
        _valid_env(),
        FAKE_LISTENER_PID="12345",
    )

    assert result.returncode == 1
    assert "non-Docker process (PID 12345)" in result.stderr
