#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
TOKEN="${2:-}"
BODY='{"session_id":null,"message":"Что за OXF01612?","answer_style":"short"}'

if [ -n "$TOKEN" ]; then
  RESP=$(curl -fsS -X POST "$BASE_URL/api/chat" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$BODY")
else
  RESP=$(curl -fsS -X POST "$BASE_URL/api/chat" -H "Content-Type: application/json" -d "$BODY")
fi

python3 -c "import json,sys; d=json.loads(sys.argv[1]); assert d.get('answer'); assert isinstance(d.get('sources',[]), list);" "$RESP"
echo "[OK] rag smoke passed"
