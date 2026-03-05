#!/bin/bash
# 🎒 Provara Master Sync Script — "The Vault of Truth" (Consolidated Edition)

VAULT_MASTER="/home/syncshadow7/master-vault"
VAULT_AGENTS="/home/syncshadow7/.provara/agent-memory"
VAULT_CLAUDE="/home/syncshadow7/.claude/agent-memory"
VAULT_HEDGE="/home/syncshadow7/projects/ai-hedge-fund/data/signal_vault"
KESTREL_DIR="/home/syncshadow7/projects/kestrel"
PROVARA_SRC="/home/syncshadow7/projects/provara/src"

echo "🏛️  Starting Master Vault Consolidation..."

# Helper for syncing via library (using Path objects)
sync_vaults() {
    src=$1
    dest=$2
    if [ -d "$src" ]; then
        echo "🔄  Syncing $src -> $dest..."
        PYTHONPATH=$PROVARA_SRC python3 -c "from pathlib import Path; from provara import sync_backpacks; sync_backpacks(Path('$src'), Path('$dest'))"
    else
        echo "🔭  Source $src not found, skipping..."
    fi
}

# 1. Sync Provara Agent Memory
sync_vaults "$VAULT_AGENTS" "$VAULT_MASTER"

# 2. Sync Claude Agent Memory
sync_vaults "$VAULT_CLAUDE" "$VAULT_MASTER"

# 3. Sync AI Hedge Fund
sync_vaults "$VAULT_HEDGE" "$VAULT_MASTER"

# 4. Consolidate Kestrel SQLite Intelligence (Non-Chain Backup)
if [ -d "$KESTREL_DIR" ]; then
    echo "📈  Backing up Kestrel SQLite Intelligence..."
    mkdir -p "$VAULT_MASTER/legacy_intel/kestrel"
    cp "$KESTREL_DIR"/*.db "$VAULT_MASTER/legacy_intel/kestrel/" 2>/dev/null
fi

# 5. Regenerate Manifest (Ensures data is "clean" for security)
echo "📜  Updating Master Manifest..."
PYTHONPATH=$PROVARA_SRC python3 -m provara.cli manifest "$VAULT_MASTER"

# 6. Verify Master
echo "🛡️  Verifying Master Vault Integrity..."
PYTHONPATH=$PROVARA_SRC python3 -m provara.cli verify "$VAULT_MASTER"

# 7. Sync to Cloud
echo "☁️  Syncing to Shrouded Cloud (Encrypted)..."
rclone sync "$VAULT_MASTER" "secret-vault:" -P

echo "✅  Master Vault is fully consolidated and shrouded! 🚀"
