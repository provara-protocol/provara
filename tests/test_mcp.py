"""Tests for the FastMCP-based Provara MCP server (src/provara/mcp.py).

Covers Provara-native tools (init_vault, verify_vault, query_events,
get_vault_status, forensic_export), resource endpoints, and PSMC
availability gating.  All tests use direct function calls — no subprocess
overhead.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from provara.mcp import (
    _PSMC_AVAILABLE,
    _vault_path,
    append_event,
    forensic_export,
    get_events_resource,
    get_status_resource,
    get_vault_status,
    init_vault,
    query_events,
    verify_chain,
    verify_vault,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def vault(tmp_path: Path) -> Path:
    """A freshly bootstrapped vault with one GENESIS event."""
    vp = tmp_path / "vault"
    result = json.loads(init_vault(str(vp)))
    assert result["success"] is True, result
    return vp


# ---------------------------------------------------------------------------
# _vault_path helper
# ---------------------------------------------------------------------------


def test_vault_path_raises_for_missing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a directory"):
        _vault_path(str(tmp_path / "nonexistent"))


def test_vault_path_returns_resolved(tmp_path: Path) -> None:
    d = tmp_path / "v"
    d.mkdir()
    resolved = _vault_path(str(d))
    assert resolved == d.resolve()


# ---------------------------------------------------------------------------
# init_vault
# ---------------------------------------------------------------------------


def test_init_vault_success(tmp_path: Path) -> None:
    result = json.loads(init_vault(str(tmp_path / "v")))
    assert result["success"] is True
    assert "key_id" in result
    assert "vault_path" in result


def test_init_vault_creates_structure(tmp_path: Path) -> None:
    vp = tmp_path / "v"
    init_vault(str(vp))
    assert (vp / "events" / "events.ndjson").exists()
    assert (vp / "identity" / "keys.json").exists()


def test_init_vault_custom_actor(tmp_path: Path) -> None:
    vp = tmp_path / "v"
    result = json.loads(init_vault(str(vp), actor_name="test_actor"))
    assert result["success"] is True


# ---------------------------------------------------------------------------
# verify_vault
# ---------------------------------------------------------------------------


def test_verify_vault_valid(vault: Path) -> None:
    result = json.loads(verify_vault(str(vault)))
    assert result["valid"] is True


def test_verify_vault_nonexistent(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a directory"):
        verify_vault(str(tmp_path / "nonexistent"))


# ---------------------------------------------------------------------------
# query_events
# ---------------------------------------------------------------------------


def test_query_events_no_filters(vault: Path) -> None:
    result = json.loads(query_events(str(vault)))
    assert "events" in result
    assert "count" in result
    assert result["count"] >= 1  # at least GENESIS


def test_query_events_by_type(vault: Path) -> None:
    result = json.loads(query_events(str(vault), event_type="GENESIS"))
    assert "events" in result
    assert result["count"] >= 1


def test_query_events_by_actor(vault: Path) -> None:
    # Bootstrap creates a "default" actor (or the actor_name passed)
    result = json.loads(query_events(str(vault), event_type="com.provara.genesis"))
    if result["events"]:
        actor = result["events"][0].get("actor")
        if actor:
            by_actor = json.loads(query_events(str(vault), actor=actor))
            assert by_actor["count"] >= 1


def test_query_events_time_range(vault: Path) -> None:
    result = json.loads(
        query_events(
            str(vault),
            after="2000-01-01T00:00:00Z",
            before="2999-12-31T23:59:59Z",
        )
    )
    assert "events" in result
    assert result["count"] >= 1


def test_query_events_empty_type_filter(vault: Path) -> None:
    result = json.loads(query_events(str(vault), event_type="NONEXISTENT_TYPE"))
    assert result["count"] == 0


# ---------------------------------------------------------------------------
# get_vault_status
# ---------------------------------------------------------------------------


def test_get_vault_status_structure(vault: Path) -> None:
    result = json.loads(get_vault_status(str(vault)))
    assert "vault_path" in result
    assert "event_count" in result
    assert "actor_count" in result
    assert "actors" in result
    assert "event_types" in result
    assert "chain_heads" in result


def test_get_vault_status_event_count(vault: Path) -> None:
    result = json.loads(get_vault_status(str(vault)))
    assert result["event_count"] >= 1  # GENESIS event


def test_get_vault_status_nonexistent(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a directory"):
        get_vault_status(str(tmp_path / "nonexistent"))


# ---------------------------------------------------------------------------
# forensic_export
# ---------------------------------------------------------------------------


def test_forensic_export_success(vault: Path, tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    result = json.loads(forensic_export(str(vault), str(out)))
    assert result["success"] is True
    assert result["event_count"] >= 1
    assert "output_path" in result
    assert out.exists()
    assert (out / "verify.py").exists()
    assert (out / "README.txt").exists()
    assert (out / "verification_report.json").exists()


def test_forensic_export_already_exists_raises(vault: Path, tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    out.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        forensic_export(str(vault), str(out))


def test_forensic_export_nonexistent_vault(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not a directory"):
        forensic_export(str(tmp_path / "nonexistent"), str(tmp_path / "out"))


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------


def test_get_events_resource(vault: Path) -> None:
    result = json.loads(get_events_resource(str(vault)))
    assert "vault_path" in result
    assert "event_count" in result
    assert "events" in result
    assert result["event_count"] >= 1


def test_get_events_resource_matches_query(vault: Path) -> None:
    resource_result = json.loads(get_events_resource(str(vault)))
    query_result = json.loads(query_events(str(vault)))
    assert resource_result["event_count"] == query_result["count"]


def test_get_status_resource(vault: Path) -> None:
    result = json.loads(get_status_resource(str(vault)))
    assert "event_count" in result
    assert "actors" in result


def test_get_status_resource_matches_tool(vault: Path) -> None:
    resource_result = json.loads(get_status_resource(str(vault)))
    tool_result = json.loads(get_vault_status(str(vault)))
    assert resource_result["event_count"] == tool_result["event_count"]


# ---------------------------------------------------------------------------
# PSMC availability gating
# ---------------------------------------------------------------------------


def test_psmc_tools_raise_when_unavailable(vault: Path) -> None:
    """PSMC-backed tools raise RuntimeError if PSMC is not importable."""
    if _PSMC_AVAILABLE:
        pytest.skip("PSMC is available in this environment")

    with pytest.raises(RuntimeError, match="PSMC tools are not available"):
        verify_chain(str(vault))

    with pytest.raises(RuntimeError, match="PSMC tools are not available"):
        append_event(str(vault), "TEST", {})
