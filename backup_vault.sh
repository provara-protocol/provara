#!/usr/bin/env bash
#
# backup_vault.sh — Automated Memory Vault Backup
#
# Creates a timestamped, integrity-verified backup of your vault.
# Designed to run weekly via cron, launchd, or manually.
#
# Usage:
#   ./backup_vault.sh                              # Defaults
#   ./backup_vault.sh ~/My_Backpack ~/Backups      # Custom paths
#   ./backup_vault.sh ~/My_Backpack /mnt/usb       # To external drive
#
# What it does:
#   1. Runs 17 integrity checks on the source vault
#   2. Creates a timestamped zip: Backup_2026-02-13_143022.zip
#   3. Verifies the zip by extracting and re-checking
#   4. Writes a SHA-256 hash file alongside the zip
#   5. Prunes old backups beyond the retention limit
#
# Automate (cron):
#   0 3 * * 0 /path/to/backup_vault.sh >> /path/to/backup.log 2>&1
#
# Automate (macOS launchd):
#   See comments at bottom of this file.
#

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_BIN="${SCRIPT_DIR}/SNP_Core/bin"
CORE_TEST="${SCRIPT_DIR}/SNP_Core/test"

VAULT_PATH="${1:-${SCRIPT_DIR}/My_Backpack}"
BACKUP_DIR="${2:-${SCRIPT_DIR}/Backups}"
MAX_BACKUPS="${3:-12}"  # Keep last 12 backups (~3 months weekly)

TIMESTAMP="$(date +%Y-%m-%d_%H%M%S)"
BACKUP_NAME="Backup_${TIMESTAMP}"
BACKUP_ZIP="${BACKUP_DIR}/${BACKUP_NAME}.zip"
BACKUP_HASH="${BACKUP_DIR}/${BACKUP_NAME}.sha256"

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

if [ -t 1 ]; then
    G='\033[0;32m' Y='\033[1;33m' R='\033[0;31m' B='\033[1m' N='\033[0m'
else
    G='' Y='' R='' B='' N=''
fi

log()  { echo -e "  [backup] $1"; }
ok()   { echo -e "  ${G}✓${N} $1"; }
warn() { echo -e "  ${Y}⚠${N} $1"; }
fail() { echo -e "  ${R}✗${N} $1"; }

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

echo ""
echo -e "${B}╔══════════════════════════════════════╗${N}"
echo -e "${B}║      Memory Vault — Weekly Backup    ║${N}"
echo -e "${B}╚══════════════════════════════════════╝${N}"
echo ""
log "Source:  ${VAULT_PATH}"
log "Target:  ${BACKUP_DIR}"
log "Time:    ${TIMESTAMP}"
echo ""

# Check vault exists
if [ ! -d "${VAULT_PATH}" ]; then
    fail "Vault not found at ${VAULT_PATH}"
    echo "  Run init_backpack.sh first, or specify the correct path."
    exit 1
fi

# Check events file exists (minimum viable vault)
if [ ! -f "${VAULT_PATH}/events/events.ndjson" ]; then
    fail "Not a valid vault (missing events/events.ndjson)"
    exit 1
fi

# Check Python + core
if ! command -v python3 &>/dev/null; then
    fail "Python 3 required but not found."
    exit 1
fi

if [ ! -f "${CORE_TEST}/backpack_compliance_v1.py" ]; then
    fail "SNP_Core test suite not found. Cannot verify integrity."
    exit 1
fi

# ---------------------------------------------------------------------------
# Step 1: Pre-backup integrity check
# ---------------------------------------------------------------------------

log "Step 1/5: Verifying source vault integrity..."

PRE_CHECK=$(PYTHONPATH="${CORE_BIN}" python3 "${CORE_TEST}/backpack_compliance_v1.py" "${VAULT_PATH}" 2>&1)
PRE_EXIT=$?

if [ $PRE_EXIT -ne 0 ]; then
    fail "Source vault FAILED integrity checks. Backup aborted."
    echo ""
    echo "  This means your vault may be corrupted or tampered with."
    echo "  Fix the issue before backing up (see Recovery/WHAT_TO_DO.md)."
    echo ""
    echo "  Details:"
    echo "${PRE_CHECK}" | grep -E "FAIL|ERROR" | head -5
    exit 2
fi

ok "Source vault: 17/17 checks passed"

# ---------------------------------------------------------------------------
# Step 2: Create backup
# ---------------------------------------------------------------------------

log "Step 2/5: Creating backup archive..."

mkdir -p "${BACKUP_DIR}"

# Zip the vault (exclude OS junk files)
cd "$(dirname "${VAULT_PATH}")"
VAULT_BASENAME="$(basename "${VAULT_PATH}")"

zip -r "${BACKUP_ZIP}" "${VAULT_BASENAME}" \
    -x "${VAULT_BASENAME}/.DS_Store" \
    -x "${VAULT_BASENAME}/*/.DS_Store" \
    -x "${VAULT_BASENAME}/Thumbs.db" \
    -x "${VAULT_BASENAME}/*/Thumbs.db" \
    -x "${VAULT_BASENAME}/__pycache__/*" \
    -x "${VAULT_BASENAME}/*/__pycache__/*" \
    > /dev/null 2>&1

BACKUP_SIZE=$(du -h "${BACKUP_ZIP}" | cut -f1)
ok "Archive created: ${BACKUP_ZIP} (${BACKUP_SIZE})"

# ---------------------------------------------------------------------------
# Step 3: Hash the backup
# ---------------------------------------------------------------------------

log "Step 3/5: Computing SHA-256 hash..."

SHA=$(shasum -a 256 "${BACKUP_ZIP}" | cut -d' ' -f1)
echo "${SHA}  $(basename "${BACKUP_ZIP}")" > "${BACKUP_HASH}"

ok "Hash: ${SHA}"

# ---------------------------------------------------------------------------
# Step 4: Verify backup (extract to temp, re-check)
# ---------------------------------------------------------------------------

log "Step 4/5: Verifying backup integrity..."

VERIFY_TMP=$(mktemp -d)
trap "rm -rf '${VERIFY_TMP}'" EXIT

unzip -q "${BACKUP_ZIP}" -d "${VERIFY_TMP}"
EXTRACTED="${VERIFY_TMP}/${VAULT_BASENAME}"

POST_CHECK=$(PYTHONPATH="${CORE_BIN}" python3 "${CORE_TEST}/backpack_compliance_v1.py" "${EXTRACTED}" 2>&1)
POST_EXIT=$?

if [ $POST_EXIT -ne 0 ]; then
    fail "Backup FAILED verification after extraction!"
    echo "  The backup archive may be corrupted. Do NOT rely on it."
    echo "  Details:"
    echo "${POST_CHECK}" | grep -E "FAIL|ERROR" | head -5
    rm -f "${BACKUP_ZIP}" "${BACKUP_HASH}"
    exit 3
fi

ok "Backup verified: 17/17 checks passed after extraction"

# ---------------------------------------------------------------------------
# Step 5: Prune old backups
# ---------------------------------------------------------------------------

log "Step 5/5: Pruning old backups (keeping last ${MAX_BACKUPS})..."

BACKUP_COUNT=$(ls -1 "${BACKUP_DIR}"/Backup_*.zip 2>/dev/null | wc -l | tr -d ' ')

if [ "${BACKUP_COUNT}" -gt "${MAX_BACKUPS}" ]; then
    PRUNE_COUNT=$((BACKUP_COUNT - MAX_BACKUPS))
    # Delete oldest backups (sorted by name = sorted by date)
    ls -1 "${BACKUP_DIR}"/Backup_*.zip | head -n "${PRUNE_COUNT}" | while read -r old_zip; do
        old_hash="${old_zip%.zip}.sha256"
        rm -f "${old_zip}" "${old_hash}"
        log "  Pruned: $(basename "${old_zip}")"
    done
    ok "Pruned ${PRUNE_COUNT} old backup(s)"
else
    ok "No pruning needed (${BACKUP_COUNT}/${MAX_BACKUPS} slots used)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo -e "${G}╔══════════════════════════════════════════════════╗${N}"
echo -e "${G}║  ✓ Backup complete and verified.                 ║${N}"
echo -e "${G}╚══════════════════════════════════════════════════╝${N}"
echo ""
echo "  Archive:  ${BACKUP_ZIP}"
echo "  Hash:     ${SHA}"
echo "  Size:     ${BACKUP_SIZE}"
echo "  Backups:  $(ls -1 "${BACKUP_DIR}"/Backup_*.zip 2>/dev/null | wc -l | tr -d ' ')/${MAX_BACKUPS}"
echo ""

# ---------------------------------------------------------------------------
# macOS launchd automation (save as ~/Library/LaunchAgents/com.snp.backup.plist):
#
# <?xml version="1.0" encoding="UTF-8"?>
# <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
# <plist version="1.0">
# <dict>
#   <key>Label</key>
#   <string>com.snp.backup</string>
#   <key>ProgramArguments</key>
#   <array>
#     <string>/path/to/backup_vault.sh</string>
#   </array>
#   <key>StartCalendarInterval</key>
#   <dict>
#     <key>Weekday</key><integer>0</integer>
#     <key>Hour</key><integer>3</integer>
#     <key>Minute</key><integer>0</integer>
#   </dict>
#   <key>StandardOutPath</key>
#   <string>/tmp/snp_backup.log</string>
#   <key>StandardErrorPath</key>
#   <string>/tmp/snp_backup.log</string>
# </dict>
# </plist>
#
# Load with: launchctl load ~/Library/LaunchAgents/com.snp.backup.plist
# ---------------------------------------------------------------------------
