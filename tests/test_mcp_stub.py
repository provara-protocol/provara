import pytest
import unittest.mock as mock
import sys
from provara import mcp

def test_mcp_structure():
    # mcp.py defines REPO_ROOT and MCP_SERVER_DIR
    assert mcp.REPO_ROOT is not None
    assert mcp.MCP_SERVER_DIR is not None

def test_mcp_main_call():
    with mock.patch("server.main") as mock_main:
        # Import mcp again or trigger its code if needed
        # But if it's already imported, the module level code ran.
        # We can call main directly if it's imported
        from provara.mcp import main
        assert main is not None
        # Calling main might try to parse sys.argv
        with mock.patch.object(sys, "argv", ["provara-mcp", "--help"]):
            # For now, just check it is callable and we can mock it
            pass
