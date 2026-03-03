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

echo "[smoke] Starting container (NUM_TEAMMATES=2 to verify configurable teammates)..."
NUM_TEAMMATES=2 docker compose -f "$COMPOSE_FILE" up -d "$SERVICE"

echo "[smoke] Waiting for healthcheck (up to ${TIMEOUT}s)..."
elapsed=0
while [ "$elapsed" -lt "$TIMEOUT" ]; do
  status=$(docker compose -f "$COMPOSE_FILE" ps --format json "$SERVICE" 2>/dev/null \
    | python3 -c "import sys,json; lines=[l for l in sys.stdin if l.strip()]; d=json.loads(lines[0]) if lines else {}; print(d.get('Health',''))" 2>/dev/null || echo "")
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

if echo "$sessions" | grep -q "lead-agent"; then
  echo "[smoke] PASS: lead-agent tmux session is running"
else
  echo "[smoke] FAIL: lead-agent tmux session not found"
  echo "[smoke] Sessions: $sessions"
  exit 1
fi

if echo "$sessions" | grep -q "teammate-1" && echo "$sessions" | grep -q "teammate-2"; then
  echo "[smoke] PASS: teammate tmux sessions are running (teammate-1, teammate-2)"
else
  echo "[smoke] FAIL: expected teammate-1 and teammate-2 sessions not found"
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

# Verify MCP tools are callable from inside the container
echo "[smoke] Checking MCP tools invocation..."
mcp_tools_check=$(docker compose -f "$COMPOSE_FILE" exec "$SERVICE" python -c "
import base64, json
from mcp.src import handlers
from mcp.src.server import handle_request
handlers.reset()
# submit_bitmap
data = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwADhQGAWjR9awAAAABJRU5ErkJggg==')
req = {'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'submit_bitmap','arguments':{'image_data':base64.b64encode(data).decode()}}}
resp = handle_request(req)
data = json.loads(resp['result']['content'][0]['text'])
key = data['cache_key']
# display_bitmap
req2 = {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'display_bitmap','arguments':{'cache_key':key,'blocking':False}}}
resp2 = handle_request(req2)
data2 = json.loads(resp2['result']['content'][0]['text'])
assert data2['success'], 'display_bitmap failed'
# get_screenshot
req3 = {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'get_screenshot','arguments':{}}}
resp3 = handle_request(req3)
data3 = json.loads(resp3['result']['content'][0]['text'])
assert 'screenshot' in data3, 'get_screenshot missing screenshot'
print('ok')
" 2>/dev/null || echo "")
if [ "$mcp_tools_check" = "ok" ]; then
  echo "[smoke] PASS: MCP tools (submit_bitmap, display_bitmap, get_screenshot) work inside container"
else
  echo "[smoke] FAIL: MCP tools invocation failed"
  exit 1
fi

echo ""
echo "[smoke] All checks passed!"
