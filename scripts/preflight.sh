#!/bin/sh

set -eu

repository_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_dir"

env_file=${VAA_ENV_FILE:-.env}

fail() {
    printf 'Preflight failed: %s\n' "$1" >&2
    exit 1
}

env_value() {
    awk -v requested_key="$1" '
        /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
        {
            separator = index($0, "=")
            if (separator == 0) { next }
            key = substr($0, 1, separator - 1)
            value = substr($0, separator + 1)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
            if (key == requested_key) {
                if (length(value) >= 2 && ((substr(value, 1, 1) == "\"" && substr(value, length(value), 1) == "\"") || (substr(value, 1, 1) == "\047" && substr(value, length(value), 1) == "\047"))) {
                    value = substr(value, 2, length(value) - 2)
                }
                print value
                exit
            }
        }
    ' "$env_file"
}

require_real_value() {
    variable_name=$1
    value=$(env_value "$variable_name")
    case "$value" in
        ""|*replace-with*|*example.com*)
            fail "$variable_name is missing or still uses the template placeholder in $env_file."
            ;;
    esac
}

command -v docker >/dev/null 2>&1 || fail "Docker is not installed or is not on PATH."
docker info >/dev/null 2>&1 || fail "Docker Desktop is not running or is not accessible."
docker compose version >/dev/null 2>&1 || fail "Docker Compose is unavailable."
[ -f "$env_file" ] || fail "$env_file does not exist; copy .env.example and fill it first."

require_real_value ZHIPU_API_KEY
require_real_value TAVILY_API_KEY
require_real_value ARXIV_PAPER_SEARCH_CLIENT_IDENTITY
require_real_value ARXIV_PAPER_CONTENT_FETCH_CLIENT_IDENTITY

if [ "${ALLOW_LEGACY_CONTAINERS:-0}" != "1" ]; then
    for legacy_name in vaa-postgres vaa-redis; do
        if docker container inspect "$legacy_name" >/dev/null 2>&1; then
            fail "legacy container $legacy_name still exists; run 'make adopt-local-data CONFIRM_ADOPT=YES' once."
        fi
    done
fi

api_port=$(env_value API_PORT)
postgres_port=$(env_value POSTGRES_PORT)
redis_port=$(env_value REDIS_PORT)
api_port=${api_port:-8000}
postgres_port=${postgres_port:-5432}
redis_port=${redis_port:-6379}

check_docker_port() {
    port=$1
    expected_container=$2
    allowed_legacy_container=${3:-}
    owners=$(docker ps --filter "publish=$port" --format '{{.Names}}')
    if [ -z "$owners" ]; then
        if command -v lsof >/dev/null 2>&1; then
            listener_pids=$(lsof -nP -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
            [ -z "$listener_pids" ] || fail "host port $port is already used by a non-Docker process (PID $listener_pids)."
        fi
        return 0
    fi
    for owner in $owners; do
        if [ "$owner" = "$expected_container" ]; then
            continue
        fi
        if [ "${ALLOW_LEGACY_CONTAINERS:-0}" = "1" ] && [ "$owner" = "$allowed_legacy_container" ]; then
            continue
        fi
        fail "host port $port is already published by Docker container $owner."
    done
}

check_docker_port "$api_port" vaa-api-1
check_docker_port "$postgres_port" vaa-postgres-1 vaa-postgres
check_docker_port "$redis_port" vaa-redis-1 vaa-redis

printf 'Preflight checks passed.\n'
