#!/bin/bash
# Build script for Provara IETF Internet-Draft
# Converts XML to text and HTML formats using xml2rfc

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
XML_FILE="$REPO_ROOT/docs/draft-hunt-provara-protocol-00.xml"
OUTPUT_DIR="$SCRIPT_DIR/output"

echo "=== Provara IETF Internet-Draft Build ==="
echo "XML source: $XML_FILE"
echo "Output directory: $OUTPUT_DIR"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check for xml2rfc
if ! command -v xml2rfc &> /dev/null; then
    echo "ERROR: xml2rfc not found. Install with:"
    echo "  pip install xml2rfc"
    exit 1
fi

echo ""
echo "Building text format..."
xml2rfc "$XML_FILE" --text --out "$OUTPUT_DIR/draft-hunt-provara-protocol-00.txt"

echo "Building HTML format..."
xml2rfc "$XML_FILE" --html --out "$OUTPUT_DIR/draft-hunt-provara-protocol-00.html"

echo "Building expanded XML..."
xml2rfc "$XML_FILE" --prepped --out "$OUTPUT_DIR/draft-hunt-provara-protocol-00.prepped.xml"

echo ""
echo "=== Build Complete ==="
echo ""
echo "Output files:"
ls -la "$OUTPUT_DIR"
echo ""
echo "To submit to IETF:"
echo "  1. Review $OUTPUT_DIR/draft-hunt-provara-protocol-00.txt"
echo "  2. Go to https://datatracker.ietf.org/submit/"
echo "  3. Upload the .txt file"
echo ""
