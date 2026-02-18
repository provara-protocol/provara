"""Smoke tests for the provara.mcp module structure and main entry point."""

import sys
import unittest.mock as mock

from provara import mcp


def test_mcp_server_instance() -> None:
    """The FastMCP server instance is exposed as provara.mcp.mcp."""
    assert mcp.mcp is not None
    assert mcp.mcp.name == "provara-vault"


def test_mcp_main_callable() -> None:
    """main() is importable and callable."""
    from provara.mcp import main

    assert callable(main)


def test_mcp_main_accepts_argv() -> None:
    """main() parses argv without error when given --help (exits SystemExit)."""
    import pytest

    with pytest.raises(SystemExit):
        mcp.main(["--help"])
