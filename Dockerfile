# BUILD STAGE
FROM python:3.12-slim AS builder

WORKDIR /app

# Copy source
COPY src/ ./src/
COPY tools/ ./tools/
COPY pyproject.toml .
COPY README.md .

# Install the package in editable mode with mcp dependencies for testing
RUN pip install --no-cache-dir -e ".[mcp]"

# RUN TESTS (Optional: can be disabled if CI handles it)
# RUN python -m pytest src/

# FINAL STAGE
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY tools/ ./tools/
COPY pyproject.toml .

# Metadata
LABEL org.opencontainers.image.title="Provara Server"
LABEL org.opencontainers.image.description="MCP server and CLI for the Provara Protocol"
LABEL org.opencontainers.image.vendor="Hunt Information Systems LLC"

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health')" || exit 1

# Default port for SSE
EXPOSE 8765

# Default command: run the MCP server in HTTP/SSE mode
ENTRYPOINT ["python", "tools/mcp_server/server.py"]
CMD ["--transport", "http", "--host", "0.0.0.0", "--port", "8765"]
