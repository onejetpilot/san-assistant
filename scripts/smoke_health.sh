#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
LAST_ERR=""
for i in $(seq 1 30); do
  if RESP=$(curl -fsS "$BASE_URL/api/health" 2>/tmp/smoke_health_err.log); then
    python3 -c "import json,sys; d=json.loads(sys.argv[1]); assert d.get('status')=='ok', d" "$RESP"
    echo "[OK] health smoke passed"
    exit 0
  fi
  LAST_ERR=$(cat /tmp/smoke_health_err.log || true)
  sleep 2
done

echo "[ERROR] health smoke failed for $BASE_URL/api/health"
if [ -n "$LAST_ERR" ]; then
  echo "[ERROR] last curl error: $LAST_ERR"
fi
exit 1
