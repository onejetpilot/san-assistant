#!/usr/bin/env bash
set -euo pipefail

cd /opt/san-assistant
git fetch origin main
git reset --hard origin/main
mkdir -p /opt/san-assistant-data
docker compose -f docker-compose.yml -f docker-compose.prod.yml config >/dev/null
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
curl -fsS http://localhost:8000/api/health >/dev/null
echo "[OK] deploy completed"
