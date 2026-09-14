#!/bin/sh

set -eu

[ "${CONFIRM_PAID:-}" = "YES" ] || {
    printf 'Refusing to call paid providers without CONFIRM_PAID=YES.\n' >&2
    exit 1
}

repository_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_dir"

api_port=$(awk -F= '$1 == "API_PORT" { gsub(/[[:space:]]/, "", $2); print $2; exit }' .env)
api_port=${api_port:-8000}

curl --fail-with-body --silent --show-error --max-time 600 \
    --header 'content-type: application/json' \
    --data '{"query":"What is retrieval-augmented generation, and what problem does it solve? Cite reliable sources.","user_id":"local-live-smoke","iteration_budget":1}' \
    "http://127.0.0.1:$api_port/v1/agent/run"
printf '\nPaid live smoke request completed.\n'
