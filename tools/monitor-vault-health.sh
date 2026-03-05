#!/bin/bash
set -e

LOGFILE="/home/syncshadow7/provara/logs/vault-health.log"
mkdir -p "$(dirname "$LOGFILE")"
echo "[$(date)] Vault health check started" >> "$LOGFILE"

/home/syncshadow7/provara/tools/verify-and-optimize.sh >> "$LOGFILE" 2>&1

if docker compose -f /home/syncshadow7/ai-hedge-fund-workspace/ai-hedge-fund/docker-compose.yml ps | grep -q "Up"; then
    echo "✅ Containers healthy" >> "$LOGFILE"
else
    echo "⚠️ Container issue detected" >> "$LOGFILE"
    exit 1
fi
