#!/usr/bin/env bash
# backup_vault.sh
# Creates an encrypted backup of the Provara vault using age or falls back to standard tar.gz.

VAULT_DIR="${1:-$HOME/.provara/agent-memory}"
BACKUP_DIR="${2:-$HOME/.provara/backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

mkdir -p "$BACKUP_DIR"

if command -v age >/dev/null 2>&1; then
    echo "📦 Creating age-encrypted backup of $VAULT_DIR..."
    tar -czC "$(dirname "$VAULT_DIR")" "$(basename "$VAULT_DIR")" | age -p > "$BACKUP_DIR/agent-memory_$TIMESTAMP.tar.gz.age"
    echo "✅ Backup created at $BACKUP_DIR/agent-memory_$TIMESTAMP.tar.gz.age"
elif command -v gpg >/dev/null 2>&1; then
    echo "📦 Creating GPG-encrypted backup of $VAULT_DIR..."
    tar -czC "$(dirname "$VAULT_DIR")" "$(basename "$VAULT_DIR")" | gpg --symmetric --cipher-algo AES256 -o "$BACKUP_DIR/agent-memory_$TIMESTAMP.tar.gz.gpg"
    echo "✅ Backup created at $BACKUP_DIR/agent-memory_$TIMESTAMP.tar.gz.gpg"
else
    echo "⚠️ Warning: 'age' or 'gpg' not found. Creating UNENCRYPTED compressed backup."
    tar -czf "$BACKUP_DIR/agent-memory_$TIMESTAMP.tar.gz" -C "$(dirname "$VAULT_DIR")" "$(basename "$VAULT_DIR")"
    echo "✅ Backup created at $BACKUP_DIR/agent-memory_$TIMESTAMP.tar.gz"
fi
