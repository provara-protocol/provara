# Provara SaaS Backend Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy protocol source and SaaS code
COPY src/ /app/src/
COPY pyproject.toml /app/

# Install the protocol and dependencies
RUN pip install --no-cache-dir -e .
RUN pip install --no-cache-dir fastapi uvicorn pydantic pydantic-settings

# Create data directory for persistent volume
RUN mkdir -p /app/data/vaults

# Set environment variables
ENV PYTHONPATH=/app/src
ENV PROVARA_VAULT_ROOT=/app/data/vaults

EXPOSE 8001

# Run the SaaS backend
CMD ["uvicorn", "provara.saas.main:app", "--host", "0.0.0.0", "--port", "8001"]
