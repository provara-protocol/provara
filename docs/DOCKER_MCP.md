# Docker MCP Server (Lane 4C)

**Status:** ✅ Complete  
**Date:** 2026-02-18  
**Platforms:** linux/amd64, linux/arm64

## Overview

The Provara Docker image provides a production-ready container with:
- MCP server (HTTP/SSE transport)
- CLI tools (`provara` command)
- PSMC tools (`psmc.py`)
- Full test suite (run during build)

## Quick Start

### Build

```bash
docker build -t provara/mcp-server:local .
```

### Run

```bash
docker run --rm -p 8765:8765 provara/mcp-server:local
```

The server starts on `http://0.0.0.0:8765/sse`.

### Health Check

```bash
curl http://localhost:8765/health
```

Response:
```json
{"ok":true,"server":"provara-mcp"}
```

## Docker Compose

Use the included `docker-compose.yml` for local development:

```bash
docker compose up --build
```

This mounts `./vault` to `/app/vault` for persistent storage.

### Compose File

```yaml
services:
  provara-server:
    build: .
    ports:
      - "8765:8765"
    volumes:
      - ./vault:/app/vault
    environment:
      - PROVARA_VAULT_PATH=/app/vault
    restart: unless-stopped
```

## Build Details

### Multi-Stage Build

The `Dockerfile` uses a two-stage build:

**Stage 1: Builder**
```dockerfile
FROM python:3.12-slim AS builder
# Install dependencies
# Copy source
# Run tests (build gate)
```

**Stage 2: Runtime**
```dockerfile
FROM python:3.12-slim
# Copy installed packages from builder
# Copy application code
# Set entrypoint
```

### Build-Time Test Gate

Tests run during the build to ensure only working images are produced:

```dockerfile
# In builder stage
RUN python -m pytest tools/mcp_server/test_server.py -v
```

If tests fail, the build fails.

## Image Metadata

The image includes OCI-compliant labels:

```dockerfile
LABEL org.opencontainers.image.title="Provara Server"
LABEL org.opencontainers.image.description="MCP server and CLI for the Provara Protocol"
LABEL org.opencontainers.image.vendor="Hunt Information Systems LLC"
```

## Image Size

Check image size:

```bash
docker image inspect provara/mcp-server:local --format='{{.Size}}'
```

Typical size: ~150-200 MB (slim Python base + cryptography dependency)

## Startup Time

Measure startup time:

```bash
# Linux/macOS
time docker run --rm -p 8765:8765 provara/mcp-server:local

# Windows PowerShell
Measure-Command { docker run --rm -p 8765:8765 provara/mcp-server:local }
```

Typical startup: <2 seconds to healthy endpoint.

## CI/CD

GitHub Actions workflow: `.github/workflows/docker-mcp.yml`

### Features

- **Multi-platform build** — amd64 and arm64
- **Smoke test** — Health check verification
- **Metrics output** — Image size and startup time in build summary

### Trigger Paths

The workflow runs on changes to:
- `Dockerfile`
- `docker-compose.yml`
- `tools/mcp_server/**`
- `tools/psmc/**`
- `src/provara/**`
- `pyproject.toml`

## Usage Examples

### Append Event via MCP

```bash
# Start server
docker run --rm -p 8765:8765 -v ./vault:/app/vault provara/mcp-server:local

# In another terminal, use MCP client or curl:
curl -X POST http://localhost:8765/message?session_id=YOUR_SESSION \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "append_event",
      "arguments": {
        "vault_path": "/app/vault",
        "event_type": "note",
        "data": {"message": "Hello from Docker"}
      }
    }
  }'
```

### CLI Access

Run CLI commands inside the container:

```bash
docker run --rm -v ./vault:/app/vault provara/mcp-server:local \
  python -m provara.cli replay --path /app/vault
```

Or use the installed `provara` command:

```bash
docker run --rm -v ./vault:/app/vault provara/mcp-server:local \
  provara replay /app/vault
```

## Security Considerations

1. **No root user** — Container runs as default user
2. **Minimal base** — python:3.12-slim reduces attack surface
3. **No secrets in image** — Private keys mounted at runtime
4. **Read-only recommended** — For production, consider `--read-only` with tmpfs

### Production Hardening

```bash
docker run --rm \
  -p 8765:8765 \
  -v ./vault:/app/vault:ro \
  -v ./keys:/app/keys:ro \
  --read-only \
  --tmpfs /tmp \
  --cap-drop=ALL \
  provara/mcp-server:local
```

## Troubleshooting

### Container Won't Start

Check logs:
```bash
docker logs <container_id>
```

### Health Check Fails

Verify port binding:
```bash
docker inspect <container_id> | grep -A 10 Ports
```

### Vault Permission Issues

Ensure mounted directory has correct permissions:
```bash
ls -la ./vault
```

## Related Documentation

- [`docs/MCP_MIGRATION.md`](MCP_MIGRATION.md) — FastMCP migration details
- [`tools/mcp_server/server.py`](../tools/mcp_server/server.py) — Server source
- [`.github/workflows/docker-mcp.yml`](../.github/workflows/docker-mcp.yml) — CI workflow
