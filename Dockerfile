# BUILD STAGE
FROM python:3.12-slim AS builder

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/
COPY tools/ ./tools/
COPY pyproject.toml .
COPY README.md .

# Install the package in editable mode for testing
RUN pip install -e .

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

# Default port for SSE
EXPOSE 8765

# Default command: run the MCP server in HTTP/SSE mode
ENTRYPOINT ["python", "tools/mcp_server/server.py"]
CMD ["--transport", "http", "--host", "0.0.0.0", "--port", "8765"]
