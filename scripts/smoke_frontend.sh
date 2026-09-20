#!/bin/sh

set -eu

repository_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_dir"

command -v curl >/dev/null 2>&1 || {
    printf 'Frontend smoke check failed: curl is required.\n' >&2
    exit 1
}

frontend_port=${FRONTEND_PORT:-}
if [ -z "$frontend_port" ]; then
    frontend_port=$(awk -F= '$1 == "FRONTEND_PORT" { gsub(/[[:space:]]/, "", $2); print $2; exit }' .env 2>/dev/null || true)
fi
frontend_port=${frontend_port:-3000}
base_url="http://127.0.0.1:$frontend_port"

curl --fail --silent --show-error --max-time 10 "$base_url/" >/dev/null
printf 'frontend index: ok\n'
curl --fail --silent --show-error --max-time 10 "$base_url/projects" >/dev/null
printf 'frontend SPA fallback: ok\n'
curl --fail --silent --show-error --max-time 10 "$base_url/api/healthz" >/dev/null
printf 'frontend API proxy healthz: ok\n'
curl --fail --silent --show-error --max-time 10 "$base_url/api/readyz" >/dev/null
printf 'frontend API proxy readyz: ok\n'
printf 'Frontend smoke checks passed. No external provider request was sent.\n'
