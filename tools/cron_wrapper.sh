#!/usr/bin/env bash
# cron_wrapper.sh
# Executes a command and logs output/errors to the Provara log file.

COMMAND="$1"
LOG_FILE="/home/syncshadow7/projects/provara/logs/vault-maintenance.log"
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")

echo "[$TIMESTAMP] START: $COMMAND" >> "$LOG_FILE"

# Execute command and capture both stdout and stderr
if eval "$COMMAND" >> "$LOG_FILE" 2>&1; then
    echo "[$TIMESTAMP] SUCCESS: $COMMAND" >> "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "[$TIMESTAMP] ERROR: $COMMAND failed with exit code $EXIT_CODE" >> "$LOG_FILE"
    # Future: Add mail/alerting logic here
fi
echo "------------------------------------------------" >> "$LOG_FILE"
