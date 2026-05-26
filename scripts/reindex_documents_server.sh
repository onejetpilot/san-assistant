#!/usr/bin/env bash
set -euo pipefail

cd /opt/san-assistant-docs
git fetch origin main
git reset --hard origin/main

cd /opt/san-assistant
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python -m app.indexes.document_index --recreate

curl -fsS http://localhost:8000/api/admin/status >/dev/null || curl -fsS http://localhost:8000/api/health >/dev/null
echo "[OK] documents reindex completed"
