#!/usr/bin/env bash
#
# init_backpack.sh — Create a new Memory Vault (Backpack v1.0)
#
# Usage:
#   ./init_backpack.sh              # Creates ./My_Backpack
#   ./init_backpack.sh ~/Vaults/me  # Creates at custom path
#
# Requirements: Python 3.10+, 'cryptography' package
#   Install: pip install cryptography
#

set -euo pipefail

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CORE_BIN="$SCRIPT_DIR/SNP_Core/bin"
CORE_TEST="$SCRIPT_DIR/SNP_Core/test"
TARGET="${1:-$SCRIPT_DIR/My_Backpack}"
KEYS_FILE="$SCRIPT_DIR/my_private_keys.json"

# --- Colors (if terminal supports them) ---
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN='' YELLOW='' RED='' BOLD='' NC=''
fi

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║    Memory Vault — First Time Setup   ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""

# --- Check Python ---
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}Error: Python 3 is required but not found.${NC}"
    echo "Install Python from https://python.org and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  Python: $PYTHON_VERSION"

# --- Check cryptography library ---
if ! python3 -c "import cryptography" 2>/dev/null; then
    echo -e "${YELLOW}Installing required library (cryptography)...${NC}"
    pip3 install cryptography --quiet --break-system-packages 2>/dev/null || \
    pip3 install cryptography --quiet 2>/dev/null || {
        echo -e "${RED}Error: Could not install 'cryptography' package.${NC}"
        echo "Run: pip install cryptography"
        exit 1
    }
fi
echo "  Crypto library: OK"

# --- Check target doesn't exist ---
if [ -d "$TARGET" ] && [ "$(ls -A "$TARGET" 2>/dev/null)" ]; then
    echo -e "${RED}Error: $TARGET already exists and is not empty.${NC}"
    echo "Choose a different location or remove the existing folder."
    exit 1
fi

# --- Check core exists ---
if [ ! -f "$CORE_BIN/bootstrap_v0.py" ]; then
    echo -e "${RED}Error: SNP_Core not found at $CORE_BIN${NC}"
    echo "Make sure the Legacy Kit folder structure is intact."
    exit 1
fi

echo ""
echo -e "  Creating vault at: ${BOLD}$TARGET${NC}"
echo ""

# --- Bootstrap ---
PYTHONPATH="$CORE_BIN" python3 "$CORE_BIN/bootstrap_v0.py" \
    "$TARGET" \
    --quorum \
    --private-keys "$KEYS_FILE" \
    --self-test

BOOT_EXIT=$?

echo ""

if [ $BOOT_EXIT -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✓ Your Memory Vault has been created.       ║${NC}"
    echo -e "${GREEN}║  ✓ All 17 integrity checks passed.           ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}⚠  IMPORTANT: Your private keys are in:${NC}"
    echo -e "${BOLD}   $KEYS_FILE${NC}"
    echo ""
    echo "   1. Move this file to your password manager or a safe place."
    echo "   2. Delete it from this folder after you've secured it."
    echo "   3. If you lose these keys, you lose ownership of this vault."
    echo ""
    echo "   Your vault is at: $TARGET"
    echo ""
else
    echo -e "${RED}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ✗ Something went wrong during setup.        ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════╝${NC}"
    echo ""
    echo "   Check the error messages above."
    echo "   If you need help, see Recovery/WHAT_TO_DO.md"
    exit 1
fi
