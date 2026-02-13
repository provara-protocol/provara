#!/usr/bin/env bash
#
# check_backpack.sh — Verify the integrity of an existing Memory Vault
#
# Usage:
#   ./check_backpack.sh                    # Checks ./My_Backpack
#   ./check_backpack.sh ~/Vaults/mine      # Checks custom path
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_BIN="$SCRIPT_DIR/SNP_Core/bin"
CORE_TEST="$SCRIPT_DIR/SNP_Core/test"
TARGET="${1:-$SCRIPT_DIR/My_Backpack}"

if [ -t 1 ]; then
    GREEN='\033[0;32m' YELLOW='\033[1;33m' RED='\033[0;31m'
    BOLD='\033[1m' NC='\033[0m'
else
    GREEN='' YELLOW='' RED='' BOLD='' NC=''
fi

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     Memory Vault — Integrity Check   ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""

# --- Validate inputs ---
if [ ! -d "$TARGET" ]; then
    echo -e "${RED}Error: No vault found at $TARGET${NC}"
    echo "Run init_backpack.sh first, or specify the path to your vault."
    exit 1
fi

if [ ! -f "$CORE_TEST/backpack_compliance_v1.py" ]; then
    echo -e "${RED}Error: Test suite not found at $CORE_TEST${NC}"
    exit 1
fi

echo -e "  Checking: ${BOLD}$TARGET${NC}"
echo ""

# --- Run compliance suite ---
PYTHONPATH="$CORE_BIN" python3 "$CORE_TEST/backpack_compliance_v1.py" "$TARGET" -v
CHECK_EXIT=$?

echo ""

if [ $CHECK_EXIT -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ All 17 integrity checks passed.           ║${NC}"
    echo -e "${GREEN}║    Your vault has not been tampered with.     ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
else
    echo -e "${RED}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ✗ Integrity check FAILED.                   ║${NC}"
    echo -e "${RED}║    See errors above. Your vault may be        ║${NC}"
    echo -e "${RED}║    corrupted or tampered with.                ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  If you have a backup, restore from it."
    echo "  See Recovery/WHAT_TO_DO.md for instructions."
    exit 1
fi
