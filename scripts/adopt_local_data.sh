#!/bin/sh

set -eu

repository_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repository_dir"

[ "${CONFIRM_ADOPT:-}" = "YES" ] || {
    printf 'Refusing to adopt legacy containers without CONFIRM_ADOPT=YES.\n' >&2
    exit 1
}

verify_container() {
    container_name=$1
    expected_image=$2
    expected_mount=$3

    docker container inspect "$container_name" >/dev/null 2>&1 || {
        printf 'Legacy container %s does not exist.\n' "$container_name" >&2
        exit 1
    }
    actual_image=$(docker inspect --format '{{.Config.Image}}' "$container_name")
    [ "$actual_image" = "$expected_image" ] || {
        printf 'Legacy container %s uses unexpected image %s.\n' "$container_name" "$actual_image" >&2
        exit 1
    }
    actual_mounts=$(docker inspect --format '{{range .Mounts}}{{.Name}}:{{.Destination}}{{"\n"}}{{end}}' "$container_name")
    printf '%s\n' "$actual_mounts" | grep -Fx "$expected_mount" >/dev/null || {
        printf 'Legacy container %s does not use expected volume %s.\n' "$container_name" "$expected_mount" >&2
        exit 1
    }
}

legacy_postgres_counts() {
    for table_name in project_profile_memory decision_memory action_memory preference_policy_memory research_knowledge_units; do
        row_count=$(docker exec vaa-postgres psql -U postgres -d vertical_ai_research_action_agent -Atc "SELECT count(*) FROM $table_name;")
        printf '%s=%s\n' "$table_name" "$row_count"
    done
}

compose_postgres_counts() {
    for table_name in project_profile_memory decision_memory action_memory preference_policy_memory research_knowledge_units; do
        row_count=$(compose_postgres_query "SELECT count(*) FROM $table_name;")
        printf '%s=%s\n' "$table_name" "$row_count"
    done
}

compose_postgres_query() {
    docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "$1"' sh "$1"
}

verify_container vaa-postgres pgvector/pgvector:pg16 vaa-postgres-data:/var/lib/postgresql/data
verify_container vaa-redis redis:7-alpine vaa-redis-data:/data

before_postgres=$(legacy_postgres_counts)
before_redis=$(docker exec vaa-redis redis-cli --raw DBSIZE)

printf 'Verified legacy containers and captured data counts.\n'
docker stop vaa-postgres vaa-redis >/dev/null
docker rm vaa-postgres vaa-redis >/dev/null
printf 'Removed legacy containers; named data volumes were preserved.\n'

mkdir -p logs
docker compose up --build --detach --wait

after_postgres=$(compose_postgres_counts)
after_redis=$(docker compose exec -T redis redis-cli --raw DBSIZE)
vector_present=$(compose_postgres_query "SELECT count(*) FROM pg_extension WHERE extname='vector';")
table_count=$(compose_postgres_query "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('project_profile_memory','decision_memory','action_memory','preference_policy_memory','research_knowledge_units');")

[ "$before_postgres" = "$after_postgres" ] || {
    printf 'Adoption validation failed: PostgreSQL row counts changed. Services were left running for inspection.\n' >&2
    exit 1
}
[ "$before_redis" = "$after_redis" ] || {
    printf 'Adoption validation failed: Redis key count changed. Services were left running for inspection.\n' >&2
    exit 1
}
[ "$vector_present" = "1" ] || {
    printf 'Adoption validation failed: pgvector extension is unavailable.\n' >&2
    exit 1
}
[ "$table_count" = "5" ] || {
    printf 'Adoption validation failed: expected five memory tables.\n' >&2
    exit 1
}

printf 'Legacy data adoption completed successfully.\n'
printf '%s\n' "$after_postgres"
printf 'redis_keys=%s\n' "$after_redis"
