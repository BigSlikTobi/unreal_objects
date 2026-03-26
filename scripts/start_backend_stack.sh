#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".venv/bin/activate" ]]; then
  echo "Missing .venv/bin/activate. Create the virtualenv first." >&2
  exit 1
fi

source .venv/bin/activate

export RULE_ENGINE_PERSISTENCE_PATH="${RULE_ENGINE_PERSISTENCE_PATH:-$ROOT_DIR/data/rule_engine_store.json}"

RULE_ENGINE_PATTERN="uvicorn rule_engine.app:app --port 8001 --host 0.0.0.0"
DECISION_CENTER_PATTERN="uvicorn decision_center.app:app --port 8002 --host 0.0.0.0"
MCP_PATTERN="python mcp_server/server.py --transport streamable-http --host 0.0.0.0 --port 8000 --auth-enabled --admin-api-key admin-secret"

stop_existing() {
  local pattern="$1"
  if pkill -f "$pattern" >/dev/null 2>&1; then
    sleep 1
  fi
}

cleanup() {
  for pid in "${RULE_ENGINE_PID:-}" "${DECISION_CENTER_PID:-}" "${MCP_PID:-}"; do
    if [[ -n "${pid}" ]] && kill -0 "${pid}" >/dev/null 2>&1; then
      kill "${pid}" >/dev/null 2>&1 || true
    fi
  done
}

trap cleanup EXIT INT TERM

stop_existing "$RULE_ENGINE_PATTERN"
stop_existing "$DECISION_CENTER_PATTERN"
stop_existing "$MCP_PATTERN"

echo "Starting Rule Engine on http://0.0.0.0:8001"
uvicorn rule_engine.app:app --port 8001 --host 0.0.0.0 &
RULE_ENGINE_PID=$!

echo "Starting Decision Center on http://0.0.0.0:8002"
uvicorn decision_center.app:app --port 8002 --host 0.0.0.0 &
DECISION_CENTER_PID=$!

echo "Starting Unreal Objects MCP Server on http://0.0.0.0:8000"
python mcp_server/server.py \
  --transport streamable-http \
  --host 0.0.0.0 \
  --port 8000 \
  --auth-enabled \
  --admin-api-key admin-secret &
MCP_PID=$!

wait "$RULE_ENGINE_PID" "$DECISION_CENTER_PID" "$MCP_PID"
