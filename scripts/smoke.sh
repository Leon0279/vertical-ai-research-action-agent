#!/bin/sh

set -eu

repository_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_dir"

command -v curl >/dev/null 2>&1 || {
    printf 'Smoke check failed: curl is required.\n' >&2
    exit 1
}

api_port=$(awk -F= '$1 == "API_PORT" { gsub(/[[:space:]]/, "", $2); print $2; exit }' .env)
api_port=${api_port:-8000}
base_url="http://127.0.0.1:$api_port"

curl --fail --silent --show-error --max-time 10 "$base_url/healthz" >/dev/null
printf 'healthz: ok\n'
curl --fail --silent --show-error --max-time 10 "$base_url/readyz" >/dev/null
printf 'readyz: ok\n'
curl --fail --silent --show-error --max-time 10 "$base_url/openapi.json" >/dev/null
printf 'openapi: ok\n'
curl --fail --silent --show-error --max-time 10 "$base_url/docs" >/dev/null
printf 'docs: ok\n'
printf 'Free smoke checks passed. No external provider request was sent.\n'
