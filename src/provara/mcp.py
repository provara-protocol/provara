"""provara.mcp — FastMCP-based MCP server for Provara vault operations.

Entry point registered in pyproject.toml:
    provara-mcp = "provara.mcp:main"

Transports
----------
    stdio (default) — for Claude Desktop and local agents
    sse             — for remote / browser agents
    streamable-http — for modern HTTP clients

Usage
-----
    provara-mcp                                          # stdio
    provara-mcp --transport sse --port 8765              # SSE on localhost:8765
    provara-mcp --transport streamable-http --port 9000  # HTTP on localhost:9000

Tools: Provara-native (no extra deps)
--------------------------------------
    init_vault          Create a new Provara vault
    verify_vault        Verify Ed25519 signatures + chain + Merkle
    query_events        Query events with filters (SQLite index)
    get_vault_status    Event count, actors, chain heads
    forensic_export     Self-contained evidence bundle with verify.py

Tools: PSMC-backed (monorepo only)
-------------------------------------
    append_event        Sign and append a PSMC memory event
    verify_chain        PSMC chain integrity
    generate_digest     Weekly digest Markdown
    export_digest       Alias for generate_digest
    snapshot_belief     Deterministic vault state hash
    snapshot_state      Alias for snapshot_belief
    query_timeline      PSMC events with time / type filter
    list_conflicts      High-confidence conflicting evidence
    export_markdown     Full vault history as Markdown
    checkpoint_vault    Sign and save a state snapshot

Resources
---------
    vault://{vault_path}/events   All events as JSON
    vault://{vault_path}/status   Vault summary as JSON
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


# ---------------------------------------------------------------------------
# PSMC bridging — optional, available when running from the monorepo
# ---------------------------------------------------------------------------

_PSMC_DIR = Path(__file__).resolve().parents[2] / "tools" / "psmc"
_PSMC_AVAILABLE = False

if _PSMC_DIR.is_dir() and str(_PSMC_DIR) not in sys.path:
    sys.path.insert(0, str(_PSMC_DIR))

try:
    from psmc import (
        append_event as _psmc_append_event,
        checkpoint_vault as _psmc_checkpoint_vault,
        compute_vault_state as _psmc_compute_vault_state,
        export_markdown as _psmc_export_markdown,
        generate_digest as _psmc_generate_digest,
        list_conflicts as _psmc_list_conflicts,
        query_timeline as _psmc_query_timeline,
        verify_chain as _psmc_verify_chain,
    )
    _PSMC_AVAILABLE = True
except ImportError:
    _PSMC_AVAILABLE = False


# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "provara-vault",
    instructions=(
        "Provara is a tamper-evident, append-only vault for AI agent memory. "
        "Every event is Ed25519-signed, SHA-256 chained, and RFC 8785-canonicalized. "
        "Use init_vault to create a vault, then append_event to record knowledge, "
        "verify_vault to confirm integrity, and forensic_export to produce "
        "a self-contained evidence bundle for third-party verification."
    ),
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _vault_path(path_str: str) -> Path:
    """Resolve and validate a vault path string — raises ValueError if missing."""
    vp = Path(path_str).expanduser().resolve()
    if not vp.is_dir():
        raise ValueError(f"vault_path is not a directory: {vp}")
    return vp


def _psmc_required() -> None:
    """Raise RuntimeError when PSMC tools are not importable."""
    if not _PSMC_AVAILABLE:
        raise RuntimeError(
            "PSMC tools are not available. Run from the Provara monorepo "
            "(tools/psmc/psmc.py must be importable)."
        )


# ---------------------------------------------------------------------------
# Provara-native tools
# ---------------------------------------------------------------------------


@mcp.tool()
def init_vault(vault_path: str, actor_name: str = "default") -> str:
    """Initialize a new Provara vault at the given path.

    Creates the directory structure, generates an Ed25519 keypair, and writes
    a signed GENESIS event.  Returns JSON with success status and key_id.
    """
    from provara.bootstrap_v0 import bootstrap_backpack

    vp = Path(vault_path).expanduser().resolve()
    result = bootstrap_backpack(vp, actor=actor_name, quiet=True)
    if result.success:
        return json.dumps(
            {
                "success": True,
                "vault_path": str(vp),
                "key_id": result.root_key_id,
            }
        )
    return json.dumps({"success": False, "errors": result.errors})


@mcp.tool()
def verify_vault(vault_path: str) -> str:
    """Verify the cryptographic integrity of a Provara vault.

    Checks Ed25519 signatures, SHA-256 chain linkage, Merkle root, and
    vault structure.  Returns JSON with valid (bool) and optional error.
    """
    from provara.backpack_integrity import validate_vault_structure

    vp = _vault_path(vault_path)
    try:
        validate_vault_structure(vp)
        return json.dumps({"valid": True, "vault_path": str(vp)})
    except Exception as exc:
        return json.dumps(
            {"valid": False, "error": str(exc), "vault_path": str(vp)}
        )


@mcp.tool()
def query_events(
    vault_path: str,
    actor: str | None = None,
    event_type: str | None = None,
    after: str | None = None,
    before: str | None = None,
) -> str:
    """Query vault events with optional filters backed by a SQLite index.

    Filters are AND-combined.  If no filters are given, all events are returned.
    ``after`` and ``before`` are ISO 8601 timestamp strings (inclusive).
    Returns JSON with events list and count.
    """
    from provara.query import VaultIndex
    from provara.sync_v0 import load_events

    vp = _vault_path(vault_path)

    if not any([actor, event_type, after, before]):
        events_file = vp / "events" / "events.ndjson"
        all_events: list[dict[str, Any]] = (
            load_events(events_file) if events_file.exists() else []
        )
        return json.dumps({"events": all_events, "count": len(all_events)})

    with VaultIndex(vp) as idx:
        idx.update()
        if actor and after and before:
            filtered = idx.query_by_actor_and_time(actor, after, before)
        elif actor and event_type:
            filtered = [
                e for e in idx.query_by_actor(actor) if e["type"] == event_type
            ]
        elif actor:
            filtered = idx.query_by_actor(actor)
        elif event_type:
            filtered = idx.query_by_type(event_type)
        else:
            start = after or ""
            end = before or "9999-99-99T23:59:59Z"
            filtered = idx.query_by_time_range(start, end)

    return json.dumps({"events": filtered, "count": len(filtered)})


@mcp.tool()
def get_vault_status(vault_path: str) -> str:
    """Get a vault summary: event count, actors, event types, and chain heads.

    Uses the SQLite index for fast aggregation (incremental build on first call).
    Returns JSON with vault_path, event_count, actor_count, actors dict,
    event_types dict, and chain_heads dict.
    """
    from provara.query import VaultIndex

    vp = _vault_path(vault_path)
    with VaultIndex(vp) as idx:
        idx.update()
        actors = idx.get_actor_summary()
        types = idx.get_type_summary()
        heads = idx.get_chain_heads()

    return json.dumps(
        {
            "vault_path": str(vp),
            "event_count": sum(actors.values()),
            "actor_count": len(actors),
            "actors": actors,
            "event_types": types,
            "chain_heads": heads,
        }
    )


@mcp.tool()
def forensic_export(vault_path: str, output_path: str) -> str:
    """Export a vault as a self-contained forensic evidence bundle.

    The bundle includes a standalone ``verify.py`` script requiring only the
    ``cryptography`` package to confirm signatures, chain integrity, and file
    hashes — no Provara installation needed.

    Raises an error if ``output_path`` already exists.
    Returns JSON with success, output_path, counts, and integrity status.
    """
    from provara.forensic_export import forensic_export as _fe

    vp = _vault_path(vault_path)
    op = Path(output_path).expanduser().resolve()
    if op.exists():
        raise ValueError(f"Output path already exists: {op}")
    fb = _fe(vp, op)
    return json.dumps(
        {
            "success": True,
            "output_path": str(op),
            "event_count": fb.event_count,
            "actor_count": fb.actor_count,
            "chain_integrity": fb.chain_integrity,
            "signature_integrity": fb.signature_integrity,
            "file_count": len(fb.files),
        }
    )


# ---------------------------------------------------------------------------
# PSMC-backed tools
# ---------------------------------------------------------------------------


@mcp.tool()
def append_event(
    vault_path: str,
    event_type: str,
    data: dict[str, Any],
    tags: list[str] | None = None,
    emit_provara: bool = False,
) -> str:
    """Append a signed PSMC event to a vault.

    Signs the event with the vault's active Ed25519 key and chains it to the
    previous event.  Returns JSON with event_id, hash, timestamp, state_hash.
    """
    _psmc_required()
    vp = _vault_path(vault_path)
    try:
        out = _psmc_append_event(
            vp, event_type, data, tags=tags, emit_provara=emit_provara
        )
    except SystemExit as exc:
        raise ValueError(f"append_event rejected input: {exc}") from exc
    return json.dumps(
        {
            "event_id": out.get("event_id"),
            "hash": out.get("hash"),
            "timestamp": out.get("timestamp"),
            "provara_event_id": out.get("provara_event_id"),
            "state_hash": out.get("state_hash"),
        }
    )


@mcp.tool()
def verify_chain(vault_path: str) -> str:
    """Verify PSMC hash-and-signature chain integrity.

    Returns JSON with valid (bool).
    """
    _psmc_required()
    vp = _vault_path(vault_path)
    ok = _psmc_verify_chain(vp, verbose=False)
    return json.dumps({"valid": bool(ok)})


@mcp.tool()
def generate_digest(vault_path: str, weeks: int = 1) -> str:
    """Generate a weekly digest of recent PSMC memory events as Markdown.

    Returns JSON with digest (Markdown string).
    """
    _psmc_required()
    if weeks <= 0:
        raise ValueError("weeks must be > 0")
    vp = _vault_path(vault_path)
    digest = _psmc_generate_digest(vp, weeks=weeks)
    return json.dumps({"digest": digest})


@mcp.tool()
def export_digest(vault_path: str, weeks: int = 1) -> str:
    """Alias for generate_digest — generate a weekly Markdown digest.

    Returns JSON with digest (Markdown string).
    """
    return generate_digest(vault_path, weeks=weeks)  # type: ignore[no-any-return]


@mcp.tool()
def snapshot_belief(vault_path: str) -> str:
    """Compute a deterministic PSMC vault snapshot and state hash.

    Returns JSON with the full state dict and content-addressed state_hash.
    """
    _psmc_required()
    vp = _vault_path(vault_path)
    return json.dumps(_psmc_compute_vault_state(vp))


@mcp.tool()
def snapshot_state(vault_path: str) -> str:
    """Alias for snapshot_belief — compute vault state and hash.

    Returns JSON with the full state dict and state_hash.
    """
    return snapshot_belief(vault_path)  # type: ignore[no-any-return]


@mcp.tool()
def query_timeline(
    vault_path: str,
    event_type: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    limit: int | None = None,
) -> str:
    """Query PSMC vault events with optional type and time-range filters.

    Returns JSON with events list.
    """
    _psmc_required()
    vp = _vault_path(vault_path)
    events = _psmc_query_timeline(
        vp,
        event_type=event_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    return json.dumps({"events": events})


@mcp.tool()
def list_conflicts(vault_path: str) -> str:
    """List conflicting high-confidence PSMC evidence entries.

    Returns JSON with conflicts dict mapping subject to conflicting assertions.
    """
    _psmc_required()
    vp = _vault_path(vault_path)
    conflicts = _psmc_list_conflicts(vp)
    return json.dumps({"conflicts": conflicts})


@mcp.tool()
def export_markdown(vault_path: str) -> str:
    """Export the entire PSMC vault history as formatted Markdown.

    Returns JSON with markdown (string).
    """
    _psmc_required()
    vp = _vault_path(vault_path)
    content = _psmc_export_markdown(vp)
    return json.dumps({"markdown": content})


@mcp.tool()
def checkpoint_vault(vault_path: str) -> str:
    """Sign and save a new PSMC state snapshot for faster future loading.

    Returns JSON with the checkpoint metadata dict.
    """
    _psmc_required()
    vp = _vault_path(vault_path)
    return json.dumps(_psmc_checkpoint_vault(vp))


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------


@mcp.resource("vault://{vault_path}/events")
def get_events_resource(vault_path: str) -> str:
    """Return all vault events as a JSON document.

    Resource URI: vault://<absolute-vault-path>/events
    """
    from provara.sync_v0 import load_events

    vp = _vault_path(vault_path)
    events_file = vp / "events" / "events.ndjson"
    events: list[dict[str, Any]] = (
        load_events(events_file) if events_file.exists() else []
    )
    return json.dumps(
        {
            "vault_path": str(vp),
            "event_count": len(events),
            "events": events,
        }
    )


@mcp.resource("vault://{vault_path}/status")
def get_status_resource(vault_path: str) -> str:
    """Return vault status as a JSON document.

    Resource URI: vault://<absolute-vault-path>/status
    """
    return get_vault_status(vault_path)  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Start the Provara MCP server.

    Defaults to stdio transport for Claude Desktop.  Use ``--transport sse``
    or ``--transport streamable-http`` for network-accessible deployments.
    """
    import argparse

    ap = argparse.ArgumentParser(
        description="Provara MCP server (FastMCP)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport mode",
    )
    ap.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host (sse / streamable-http only)",
    )
    ap.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Bind port (sse / streamable-http only)",
    )
    args = ap.parse_args(argv)

    if args.transport != "stdio":
        mcp.settings.host = args.host
        mcp.settings.port = args.port

    mcp.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
