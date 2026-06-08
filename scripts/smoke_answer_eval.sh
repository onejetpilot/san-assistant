#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-${APP_BASE_URL:-http://localhost:8000}}"
TOKEN="${2:-${APP_ACCESS_TOKEN:-}}"
STRICT="${LIVE_ANSWER_EVAL_STRICT:-0}"

echo "[INFO] running live answer eval against ${BASE_URL}"
set +e
if [ -n "$TOKEN" ]; then
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend \
    python -m app.evaluation.run_chat_api_eval --base-url "$BASE_URL" --token "$TOKEN"
else
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T backend \
    python -m app.evaluation.run_chat_api_eval --base-url "$BASE_URL"
fi
RC=$?
set -e

if [ "$RC" -eq 0 ]; then
  echo "[OK] live answer eval passed"
  exit 0
fi

if [ "$STRICT" = "1" ]; then
  echo "[ERROR] live answer eval failed"
  exit "$RC"
fi

echo "[WARN] live answer eval failed, continuing because LIVE_ANSWER_EVAL_STRICT is not 1"
