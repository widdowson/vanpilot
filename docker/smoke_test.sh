#!/usr/bin/env bash
# Smoke test for the consolidated VanPilot agent container.
#
# Verifies that the container builds and key services start correctly.
# Does NOT require ANTHROPIC_API_KEY.
#
# Usage: ./docker/smoke_test.sh

set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
SERVICE="agent"
TIMEOUT=60

cleanup() {
  echo "[smoke] Cleaning up..."
  docker compose -f "$COMPOSE_FILE" down --timeout 5 2>/dev/null || true
}
trap cleanup EXIT

cd "$(dirname "$0")/.."

echo "[smoke] Building container..."
docker compose -f "$COMPOSE_FILE" build "$SERVICE"

echo "[smoke] Starting container..."
docker compose -f "$COMPOSE_FILE" up -d "$SERVICE"

echo "[smoke] Waiting for healthcheck (up to ${TIMEOUT}s)..."
elapsed=0
while [ "$elapsed" -lt "$TIMEOUT" ]; do
  status=$(docker compose -f "$COMPOSE_FILE" ps --format json "$SERVICE" 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Health',''))" 2>/dev/null || echo "")
  if [ "$status" = "healthy" ]; then
    echo "[smoke] PASS: container is healthy"
    break
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done

if [ "$elapsed" -ge "$TIMEOUT" ]; then
  echo "[smoke] FAIL: healthcheck did not pass within ${TIMEOUT}s"
  echo "[smoke] Container logs:"
  docker compose -f "$COMPOSE_FILE" logs "$SERVICE"
  exit 1
fi

# Verify tmux sessions are running
echo "[smoke] Checking tmux sessions..."
sessions=$(docker compose -f "$COMPOSE_FILE" exec "$SERVICE" tmux list-sessions 2>/dev/null || echo "")
if echo "$sessions" | grep -q "supervisor"; then
  echo "[smoke] PASS: supervisor tmux session is running"
else
  echo "[smoke] FAIL: supervisor tmux session not found"
  echo "[smoke] Sessions: $sessions"
  exit 1
fi

# Verify Claude Code CLI is installed
echo "[smoke] Checking Claude Code CLI..."
claude_version=$(docker compose -f "$COMPOSE_FILE" exec "$SERVICE" claude --version 2>/dev/null || echo "")
if [ -n "$claude_version" ]; then
  echo "[smoke] PASS: Claude Code CLI installed ($claude_version)"
else
  echo "[smoke] FAIL: Claude Code CLI not found"
  exit 1
fi

# Verify MCP server can start (dry run)
echo "[smoke] Checking MCP server module..."
mcp_check=$(docker compose -f "$COMPOSE_FILE" exec "$SERVICE" \
  python -c "from mcp.src.server import main; print('ok')" 2>/dev/null || echo "")
if [ "$mcp_check" = "ok" ]; then
  echo "[smoke] PASS: MCP server module importable"
else
  echo "[smoke] FAIL: MCP server module not importable"
  exit 1
fi

echo ""
echo "[smoke] All checks passed!"
