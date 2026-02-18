"""Property-based fuzzing for MCP tool input robustness."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

from provara.mcp import init_vault, query_events


def _safe_segment(raw: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in raw).strip("._")
    if not cleaned:
        return "vault"
    return cleaned[:80]


@given(st.text(min_size=0, max_size=200))
@settings(deadline=5000, max_examples=100)
def test_mcp_init_vault_handles_bad_paths(path: str) -> None:
    """MCP init_vault does not crash on arbitrary path-like strings."""
    with tempfile.TemporaryDirectory() as tmp:
        candidate = Path(tmp) / _safe_segment(path)
        try:
            raw = init_vault(str(candidate))
            result = json.loads(raw)
            assert isinstance(result, dict)
            assert "success" in result
        except Exception as exc:
            assert isinstance(exc, (OSError, ValueError))


@given(st.text(min_size=0, max_size=200), st.text(min_size=0, max_size=200))
@settings(deadline=5000, max_examples=100)
def test_mcp_query_handles_bad_input(
    actor: str,
    event_type: str,
) -> None:
    """MCP query_events does not crash on arbitrary filter strings."""
    with tempfile.TemporaryDirectory() as tmp:
        vault_path = Path(tmp) / "query_vault"
        init_result = json.loads(init_vault(str(vault_path)))
        assert "success" in init_result

        try:
            raw = query_events(str(vault_path), actor=actor, event_type=event_type)
            result = json.loads(raw)
            assert "events" in result
            assert "count" in result
        except Exception as exc:
            assert isinstance(exc, ValueError)
