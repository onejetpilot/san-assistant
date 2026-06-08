#!/usr/bin/env bash
set -euo pipefail

cd /opt/san-assistant-kb
git fetch origin main
git reset --hard origin/main

cd /opt/san-assistant
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python -m app.rag.validate_knowledge_base
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python -m app.rag.ingest --recreate
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend python -m app.evaluation.check_runtime_indexes

curl -fsS http://localhost:8000/api/admin/status >/dev/null || curl -fsS http://localhost:8000/api/health >/dev/null
if [ -x ./scripts/smoke_answer_eval.sh ]; then
  ./scripts/smoke_answer_eval.sh "${APP_BASE_URL:-http://localhost:8000}" "${APP_ACCESS_TOKEN:-}"
fi
echo "[OK] knowledge reindex completed"
