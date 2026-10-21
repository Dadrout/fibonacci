#!/usr/bin/env bash
set -euo pipefail

: "${DEPLOY_HOST:?Set DEPLOY_HOST to the API server hostname or IP}"
: "${DEPLOY_USER:?Set DEPLOY_USER to a non-root deployment user with Docker access}"
: "${REMOTE_PROJECT_DIR:?Set REMOTE_PROJECT_DIR to the checked-out project directory}"

ssh "${DEPLOY_USER}@${DEPLOY_HOST}" bash -s -- "${REMOTE_PROJECT_DIR}" <<'REMOTE'
set -euo pipefail
project_dir="$1"
cd "$project_dir"

git fetch origin main
git switch main
git pull --ff-only origin main

docker compose config --quiet
docker compose build api celery-worker
docker compose up -d --remove-orphans

for attempt in $(seq 1 20); do
  if curl -fsS https://api.wizetale.com/health >/dev/null; then
    docker compose ps
    exit 0
  fi
  sleep 3
done

docker compose ps
docker compose logs --tail=100 api nginx
exit 1
REMOTE
