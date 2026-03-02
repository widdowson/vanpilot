#!/usr/bin/env bash
# Entrypoint for the consolidated VanPilot agent container.
#
# Starts all co-located services:
#   1. tmux server
#   2. Supervisor gRPC server (in a tmux session)
#   3. Claude Code lead agent (in a tmux session, if ANTHROPIC_API_KEY is set)
#
# The MCP server is NOT started here — Claude Code spawns it on demand
# via the .mcp.json config (stdio transport).

set -euo pipefail

echo "[entrypoint] Starting VanPilot agent container..."

# Start tmux server
tmux start-server

# Start the supervisor gRPC server in a tmux session
tmux new-session -d -s supervisor bash -c '
  echo "[supervisor] Starting gRPC server on port 50051..."
  python -c "
from supervisor.src.server import create_server
import signal, sys

server, port, bridge = create_server(50051)
server.start()
print(f\"[supervisor] gRPC server listening on port {port}\", flush=True)
signal.signal(signal.SIGTERM, lambda *_: (server.stop(5), sys.exit(0)))
server.wait_for_termination()
"
'

echo "[entrypoint] Supervisor started in tmux session 'supervisor'"

# Start the Claude Code lead agent if API key is available
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  tmux new-session -d -s lead-agent bash -c '
    echo "[lead-agent] Starting Claude Code lead agent..."
    cd /workspace
    claude --accept-all
  '
  echo "[entrypoint] Claude Code lead agent started in tmux session 'lead-agent'"
else
  echo "[entrypoint] ANTHROPIC_API_KEY not set — skipping Claude Code lead agent"
  echo "[entrypoint] Set ANTHROPIC_API_KEY to enable the agent"
fi

echo "[entrypoint] All services started."

# Block forever to keep the container alive. The container's lifecycle
# is managed by docker-compose healthcheck + restart policy, not by
# individual session exits. The healthcheck probes the gRPC port and
# docker-compose restarts the container if it becomes unhealthy.
exec tail -f /dev/null
