#!/usr/bin/env bash
# verify-and-optimize.sh
# Verifies Provara vault integrity and optimizes SQLite database

VAULT_DIR="${1:-$HOME/.provara/agent-memory}"
PSMC_TOOL="$HOME/provara/tools/psmc/psmc.py"

echo "🔍 Verifying vault integrity at $VAULT_DIR..."
python3 "$PSMC_TOOL" --vault "$VAULT_DIR" verify
VERIFY_STATUS=$?

if [ $VERIFY_STATUS -ne 0 ]; then
    echo "❌ Verification failed! Chain integrity is compromised. Skipping optimization."
    exit 1
fi
echo "✅ Verification passed. Chain is fully intact."

if [ -f "$VAULT_DIR/vault.sqlite" ]; then
    echo "⚡ Optimizing vault.sqlite (WAL Checkpoint, Analyze, Vacuum)..."
    sqlite3 "$VAULT_DIR/vault.sqlite" "PRAGMA wal_checkpoint(FULL); PRAGMA optimize; VACUUM;"
    echo "✅ Optimization complete."
fi
