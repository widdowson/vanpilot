# Consolidated Dockerfile for the VanPilot agent container.
#
# Runs all co-located services in a single container:
#   - tmux (session manager)
#   - Claude Code lead agent (in a tmux session; spawns sub-agents via agent teams)
#   - Supervisory process (gRPC server on port 50051)
#   - MCP server (stdio, invoked by Claude Code via .mcp.json)
#
# Architecture: everything co-located so the supervisor can directly read
# Claude Code JSON logs (no IPC), and .mcp.json points to localhost.

# --- Builder stage: proto codegen ---
FROM python:3.12-slim AS builder

COPY supervisor/proxy-ca.crt* /tmp/
RUN if [ -s /tmp/proxy-ca.crt ]; then \
      cp /tmp/proxy-ca.crt /usr/local/share/ca-certificates/proxy-ca.crt && \
      update-ca-certificates; \
    fi

RUN pip install --no-cache-dir grpcio-tools==1.72.0

WORKDIR /build

COPY proto/vanpilot/v1/*.proto proto/vanpilot/v1/
RUN python -m grpc_tools.protoc \
    --proto_path=. \
    --python_out=. \
    proto/vanpilot/v1/sync.proto \
    proto/vanpilot/v1/display.proto \
    proto/vanpilot/v1/screenshot.proto

# --- Runtime stage ---
FROM python:3.12-slim

# Proxy CA trust (sandbox environments)
COPY supervisor/proxy-ca.crt* /tmp/
RUN if [ -s /tmp/proxy-ca.crt ]; then \
      cp /tmp/proxy-ca.crt /usr/local/share/ca-certificates/proxy-ca.crt && \
      update-ca-certificates; \
    fi
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt

# System packages: tmux for session management, curl + node for Claude Code CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (LTS) for Claude Code CLI
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Python dependencies
RUN pip install --no-cache-dir grpcio==1.72.0 "protobuf>=6.30.0"

WORKDIR /app

# Copy generated proto stubs from builder
COPY --from=builder /build/proto/ proto/

# Copy supervisor source
COPY supervisor/src/ supervisor/src/

# Copy MCP source
COPY mcp/src/ mcp/src/

# Copy .mcp.json so Claude Code discovers the MCP server
COPY .mcp.json .mcp.json

# Copy entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONPATH=/app

# Claude Code agent teams feature flag
ENV CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

EXPOSE 50051

ENTRYPOINT ["/entrypoint.sh"]
