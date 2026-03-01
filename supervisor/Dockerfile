# Dockerfile for the VanPilot supervisor process.
#
# The supervisor serves gRPC on port 50051 and manages Claude Code
# agent sessions via tmux. It requires grpcio and the generated
# protobuf Python stubs.

FROM python:3.12-slim AS builder

# Configure proxy CA trust for sandbox environments.
# proxy-ca.crt is copied from the build context (may be empty in prod).
COPY supervisor/proxy-ca.crt* /tmp/
RUN if [ -s /tmp/proxy-ca.crt ]; then \
      cp /tmp/proxy-ca.crt /usr/local/share/ca-certificates/proxy-ca.crt && \
      update-ca-certificates; \
    fi
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt

# Install protoc via grpcio-tools for proto codegen
RUN pip install --no-cache-dir grpcio-tools==1.72.0

WORKDIR /build

# Copy proto definitions and generate Python stubs
COPY proto/vanpilot/v1/*.proto proto/vanpilot/v1/
RUN python -m grpc_tools.protoc \
    --proto_path=. \
    --python_out=. \
    proto/vanpilot/v1/sync.proto \
    proto/vanpilot/v1/display.proto \
    proto/vanpilot/v1/screenshot.proto

# --- Runtime stage ---
FROM python:3.12-slim

# Configure proxy CA trust for sandbox environments
COPY supervisor/proxy-ca.crt* /tmp/
RUN if [ -s /tmp/proxy-ca.crt ]; then \
      cp /tmp/proxy-ca.crt /usr/local/share/ca-certificates/proxy-ca.crt && \
      update-ca-certificates; \
    fi
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt

RUN apt-get update && apt-get install -y --no-install-recommends \
    tmux \
    && rm -rf /var/lib/apt/lists/*

# Match protobuf version to what grpcio-tools generates (6.x).
# Use latest grpcio that works with protobuf 6.x.
RUN pip install --no-cache-dir grpcio==1.72.0 protobuf>=6.30.0

WORKDIR /app

# Copy generated proto stubs from builder
COPY --from=builder /build/proto/ proto/

# Copy supervisor source
COPY supervisor/src/__init__.py supervisor/src/__init__.py
COPY supervisor/src/server.py supervisor/src/server.py
COPY supervisor/src/sync_service.py supervisor/src/sync_service.py
COPY supervisor/src/event_store.py supervisor/src/event_store.py
COPY supervisor/src/tmux_launcher.py supervisor/src/tmux_launcher.py

ENV PYTHONPATH=/app

EXPOSE 50051

CMD ["python", "-c", "\
from supervisor.src.server import create_server; \
import signal, sys; \
server, port = create_server(50051); \
server.start(); \
print(f'Supervisor gRPC server listening on port {port}', flush=True); \
signal.signal(signal.SIGTERM, lambda *_: (server.stop(5), sys.exit(0))); \
server.wait_for_termination() \
"]
