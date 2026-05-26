#!/usr/bin/env bash
set -euo pipefail

cd /opt/san-assistant
git fetch origin main
git reset --hard origin/main
mkdir -p /opt/san-assistant-data
docker compose -f docker-compose.yml -f docker-compose.prod.yml config >/dev/null

# Remove old containers for this compose project before recreate.
docker compose -f docker-compose.yml -f docker-compose.prod.yml down --remove-orphans || true

docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
echo "[INFO] waiting for backend health..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost:8000/api/health >/dev/null; then
    # Cleanup dangling images after successful deploy to avoid disk clutter.
    docker image prune -f >/dev/null || true
    echo "[OK] backend is healthy"
    echo "[OK] deploy completed"
    exit 0
  fi
  sleep 2
done

echo "[ERROR] backend healthcheck failed after timeout"
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=200 backend || true
exit 1
