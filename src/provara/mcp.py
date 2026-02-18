"""
Provara MCP Server — entry point for `provara-mcp` command.

This module re-exports the MCP server from tools/mcp_server/server.py
to make it available as a package entry point.
"""

import sys
from pathlib import Path

# Add tools/mcp_server to path
REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_SERVER_DIR = REPO_ROOT / "tools" / "mcp_server"
if str(MCP_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER_DIR))

from server import main

if __name__ == "__main__":
    main()
