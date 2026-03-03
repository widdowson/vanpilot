#!/usr/bin/env bash
# Entrypoint for the consolidated VanPilot agent container.
#
# Starts all co-located services:
#   1. tmux server
#   2. Supervisor gRPC server (in a tmux session)
#   3. Claude Code lead agent (in a tmux session)
#   4. Claude Code teammate agents (NUM_TEAMMATES sessions, default 0)
#
# The MCP server is NOT started here — Claude Code spawns it on demand
# via the .mcp.json config (stdio transport).
#
# Environment variables:
#   NUM_TEAMMATES  Number of teammate agent sessions to launch (default: 0)

set -euo pipefail

NUM_TEAMMATES="${NUM_TEAMMATES:-0}"

echo "[entrypoint] Starting VanPilot agent container (NUM_TEAMMATES=${NUM_TEAMMATES})..."

# Start tmux server
tmux start-server

# Start the supervisor gRPC server in a tmux session
tmux new-session -d -s supervisor bash -c '
  echo "[supervisor] Starting gRPC server..."
  python -c "
from supervisor.src.server import create_server, create_android_app_client, parse_server_config
import signal, sys

host, port, app_target = parse_server_config()
app_client, app_channel = create_android_app_client(app_target)
server, actual_port, bridge, tailer = create_server(port=port, host=host, app_client=app_client)
tailer.start()
server.start()
print(f\"[supervisor] gRPC server listening on {host}:{actual_port}\", flush=True)

def shutdown(*_):
    tailer.stop()
    app_channel.close()
    server.stop(5)
    sys.exit(0)

signal.signal(signal.SIGTERM, shutdown)
server.wait_for_termination()
"
'

echo "[entrypoint] Supervisor started in tmux session 'supervisor'"

tmux new-session -d -s lead-agent bash -c '
  echo "[lead-agent] Starting Claude Code lead agent..."
  cd /workspace
  claude --accept-all
'
echo "[entrypoint] Claude Code lead agent started in tmux session 'lead-agent'"

for i in $(seq 1 "${NUM_TEAMMATES}"); do
  tmux new-session -d -s "teammate-${i}" bash -c "
    echo \"[teammate-${i}] Starting Claude Code teammate ${i}...\"
    cd /workspace
    claude --accept-all
  "
  echo "[entrypoint] Claude Code teammate ${i} started in tmux session 'teammate-${i}'"
done

echo "[entrypoint] All services started."

# Block forever to keep the container alive. The container's lifecycle
# is managed by docker-compose healthcheck + restart policy, not by
# individual session exits. The healthcheck probes the gRPC port and
# docker-compose restarts the container if it becomes unhealthy.
exec tail -f /dev/null
