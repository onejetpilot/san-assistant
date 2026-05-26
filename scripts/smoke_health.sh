#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
RESP=$(curl -fsS "$BASE_URL/api/health")
python3 -c "import json,sys; d=json.loads(sys.argv[1]); assert d.get('status')=='ok', d" "$RESP"
echo "[OK] health smoke passed"
