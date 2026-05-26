#!/usr/bin/env bash
set -euo pipefail

for d in /opt/san-assistant /opt/san-assistant-kb /opt/san-assistant-docs /opt/san-assistant-data; do
  if [ -d "$d" ]; then
    echo "[OK] exists: $d"
  else
    mkdir -p "$d"
    echo "[OK] created: $d"
  fi
done

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker is not installed" >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] docker compose plugin is not available" >&2
  exit 1
fi

echo "[OK] Docker and docker compose are available"
echo "Next steps:"
echo "  git clone https://github.com/onejetpilot/san-assistant /opt/san-assistant"
echo "  git clone https://github.com/onejetpilot/san-assistant-kb /opt/san-assistant-kb"
echo "  git clone https://github.com/onejetpilot/san-assistant-docs /opt/san-assistant-docs"
echo "  create /opt/san-assistant/.env and run docker compose"
