# Dockerfile for the VanPilot MCP display-control server.
#
# The MCP server uses JSON-RPC 2.0 over stdio. It has no external
# dependencies beyond the Python standard library.

FROM python:3.12-slim

WORKDIR /app

# Copy MCP source (context is mcp/, dest preserves module path)
COPY src/__init__.py mcp/src/__init__.py
COPY src/server.py mcp/src/server.py
COPY src/handlers.py mcp/src/handlers.py
COPY src/tools.py mcp/src/tools.py

ENV PYTHONPATH=/app

# MCP server communicates over stdio, no ports needed.
# The default command runs the server; in production this is invoked
# by Claude Code via the .mcp.json config with stdin/stdout pipes.
CMD ["python", "-m", "mcp.src.server"]
