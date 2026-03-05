"""
migrate_ndjson.py — Convert NDJSON vault events to queryable SQLite.

Faithfully archives NDJSON event fields into a single SQLite file for
querying and AI-driven visualization. Supports both Provara Backpack
format (signed events with event_id/sig) and PSMC format (hash-chained
events with id/hash/data).

Usage:
    from provara.migrate_ndjson import migrate

    result = migrate("My_Backpack", "my_vault.sqlite")
    result = migrate("~/.provara/agent-memory", "memory.sqlite")
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

from .canonical_json import canonical_dumps


# ---------------------------------------------------------------------------
# Unified schema — covers both Backpack and PSMC event formats
# ---------------------------------------------------------------------------

MIGRATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vault_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT    NOT NULL UNIQUE,
    type            TEXT    NOT NULL,
    timestamp       TEXT    NOT NULL,
    payload         TEXT    NOT NULL,
    -- Backpack fields (nullable for PSMC events)
    actor           TEXT,
    actor_key_id    TEXT,
    namespace       TEXT,
    ts_logical      INTEGER,
    prev_event_hash TEXT,
    sig             TEXT,
    raw_canonical   TEXT,
    -- PSMC fields (nullable for Backpack events)
    hash            TEXT,
    prev_hash       TEXT,
    tags            TEXT,
    -- Format provenance
    source_format   TEXT    NOT NULL DEFAULT 'unknown'
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor);
CREATE INDEX IF NOT EXISTS idx_events_tags ON events(tags);
CREATE INDEX IF NOT EXISTS idx_events_format ON events(source_format);
"""


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def _detect_format(ev: dict) -> str:
    """Detect whether an event is Backpack or PSMC format."""
    if "event_id" in ev and "sig" in ev:
        return "backpack"
    if "id" in ev and "hash" in ev:
        return "psmc"
    if "event_id" in ev:
        return "backpack"
    if "id" in ev:
        return "psmc"
    return "unknown"


def _normalize_event(ev: dict) -> dict:
    """Normalize an event from either format into unified schema fields."""
    fmt = _detect_format(ev)

    if fmt == "backpack":
        payload_raw = ev.get("payload", {})
        sig = ev.get("sig", "")
        check_ev = {k: v for k, v in ev.items() if k != "sig"}
        raw_canonical = canonical_dumps(check_ev)

        return {
            "event_id": ev["event_id"],
            "type": ev.get("type", ""),
            "timestamp": ev.get("timestamp_utc", ""),
            "payload": json.dumps(payload_raw, sort_keys=True, separators=(",", ":")),
            "actor": ev.get("actor", ""),
            "actor_key_id": ev.get("actor_key_id", ""),
            "namespace": ev.get("namespace", "canonical"),
            "ts_logical": ev.get("ts_logical", 0),
            "prev_event_hash": ev.get("prev_event_hash"),
            "sig": sig,
            "raw_canonical": raw_canonical,
            "hash": None,
            "prev_hash": None,
            "tags": None,
            "source_format": "backpack",
        }

    elif fmt == "psmc":
        data = ev.get("data", {})
        tags = ev.get("tags", [])

        return {
            "event_id": ev["id"],
            "type": ev.get("type", ""),
            "timestamp": ev.get("timestamp", ""),
            "payload": json.dumps(data, sort_keys=True, separators=(",", ":")),
            "actor": None,
            "actor_key_id": None,
            "namespace": None,
            "ts_logical": ev.get("seq"),
            "prev_event_hash": None,
            "sig": None,
            "raw_canonical": None,
            "hash": ev.get("hash", ""),
            "prev_hash": ev.get("prev_hash"),
            "tags": json.dumps(tags) if tags else None,
            "source_format": "psmc",
        }

    else:
        # Best-effort: store the whole event as payload
        eid = ev.get("event_id") or ev.get("id") or f"unknown_{hash(json.dumps(ev, sort_keys=True)) % 10**12}"
        return {
            "event_id": str(eid),
            "type": ev.get("type", "unknown"),
            "timestamp": ev.get("timestamp_utc") or ev.get("timestamp", ""),
            "payload": json.dumps(ev, sort_keys=True, separators=(",", ":")),
            "actor": ev.get("actor"),
            "actor_key_id": None,
            "namespace": None,
            "ts_logical": None,
            "prev_event_hash": None,
            "sig": None,
            "raw_canonical": None,
            "hash": ev.get("hash"),
            "prev_hash": ev.get("prev_hash"),
            "tags": None,
            "source_format": "unknown",
        }


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def migrate(
    source: str | Path,
    dest: str | Path,
    verify: bool = True,
) -> dict:
    """Convert NDJSON vault events to a queryable SQLite file.

    Auto-detects Backpack vs PSMC format per-event. Handles mixed vaults.

    Args:
        source: Path to vault directory or events.ndjson file directly.
        dest: Path for output SQLite file (created if missing).
        verify: When True, verify chain integrity after migration.

    Returns:
        Dict with migration stats.
    """
    source = Path(source)

    # Resolve to events.ndjson
    if source.is_dir():
        ndjson_path = source / "events" / "events.ndjson"
    else:
        ndjson_path = source

    if not ndjson_path.exists():
        raise FileNotFoundError(f"No events file at {ndjson_path}")

    dest = Path(dest)
    t0 = time.monotonic()

    events = list(_iter_ndjson(ndjson_path))
    conn = _init_sqlite(dest)

    actors = set()
    event_types = set()
    formats = set()
    inserted = 0
    skipped = 0

    for ev in events:
        try:
            normalized = _normalize_event(ev)
        except (KeyError, TypeError):
            skipped += 1
            continue

        fmt = normalized["source_format"]
        formats.add(fmt)
        event_types.add(normalized["type"])
        if normalized["actor"]:
            actors.add(normalized["actor"])

        try:
            conn.execute(
                """INSERT OR IGNORE INTO events
                   (event_id, type, timestamp, payload,
                    actor, actor_key_id, namespace, ts_logical,
                    prev_event_hash, sig, raw_canonical,
                    hash, prev_hash, tags, source_format)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    normalized["event_id"],
                    normalized["type"],
                    normalized["timestamp"],
                    normalized["payload"],
                    normalized["actor"],
                    normalized["actor_key_id"],
                    normalized["namespace"],
                    normalized["ts_logical"],
                    normalized["prev_event_hash"],
                    normalized["sig"],
                    normalized["raw_canonical"],
                    normalized["hash"],
                    normalized["prev_hash"],
                    normalized["tags"],
                    normalized["source_format"],
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1

    # Metadata
    conn.execute(
        "INSERT OR REPLACE INTO vault_meta (key, value) VALUES (?, ?)",
        ("migrated_from", str(ndjson_path.resolve())),
    )
    conn.execute(
        "INSERT OR REPLACE INTO vault_meta (key, value) VALUES (?, ?)",
        ("migrated_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
    )
    conn.execute(
        "INSERT OR REPLACE INTO vault_meta (key, value) VALUES (?, ?)",
        ("event_count", str(inserted)),
    )
    conn.execute(
        "INSERT OR REPLACE INTO vault_meta (key, value) VALUES (?, ?)",
        ("source_formats", json.dumps(sorted(formats))),
    )
    conn.commit()

    duration = time.monotonic() - t0

    result = {
        "count": inserted,
        "skipped": skipped,
        "formats": sorted(formats),
        "actors": sorted(actors),
        "event_types": sorted(event_types),
        "duration_s": round(duration, 3),
        "source": str(ndjson_path),
        "dest": str(dest),
    }

    if verify:
        errors = _verify_migrated_chains(conn)
        result["chain_valid"] = len(errors) == 0
        result["chain_errors"] = errors

    conn.close()
    return result


# ---------------------------------------------------------------------------
# Querying helpers (for AI / visualization use)
# ---------------------------------------------------------------------------

def open_vault(path: str | Path) -> sqlite3.Connection:
    """Open a migrated SQLite vault for querying."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def query_events(
    conn: sqlite3.Connection,
    event_type: Optional[str] = None,
    actor: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = 1000,
) -> list[dict]:
    """Query migrated events with optional filters."""
    clauses = []
    params: list = []

    if event_type:
        clauses.append("type = ?")
        params.append(event_type)
    if actor:
        clauses.append("actor = ?")
        params.append(actor)
    if since:
        clauses.append("timestamp >= ?")
        params.append(since)
    if until:
        clauses.append("timestamp <= ?")
        params.append(until)
    if tags:
        clauses.append("tags LIKE ?")
        params.append(f"%{tags}%")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    rows = conn.execute(
        f"SELECT * FROM events {where} ORDER BY timestamp ASC, event_id ASC LIMIT ?",
        params,
    ).fetchall()

    return [_row_to_dict(r) for r in rows]


def summary(conn: sqlite3.Connection) -> dict:
    """Return vault summary: counts by type, actor, format, time range."""
    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    by_type = dict(conn.execute(
        "SELECT type, COUNT(*) FROM events GROUP BY type ORDER BY COUNT(*) DESC"
    ).fetchall())

    by_actor = dict(conn.execute(
        "SELECT actor, COUNT(*) FROM events WHERE actor IS NOT NULL "
        "GROUP BY actor ORDER BY COUNT(*) DESC"
    ).fetchall())

    by_format = dict(conn.execute(
        "SELECT source_format, COUNT(*) FROM events GROUP BY source_format"
    ).fetchall())

    time_range = conn.execute(
        "SELECT MIN(timestamp), MAX(timestamp) FROM events"
    ).fetchone()

    return {
        "total_events": total,
        "by_type": by_type,
        "by_actor": by_actor,
        "by_format": by_format,
        "earliest": time_range[0],
        "latest": time_range[1],
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _iter_ndjson(path: Path):
    """Yield parsed dicts from NDJSON file, skipping blank/malformed lines."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _init_sqlite(path: Path) -> sqlite3.Connection:
    """Create and initialize migration SQLite database."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.executescript(MIGRATE_SCHEMA_SQL)
    conn.commit()
    return conn


def _verify_migrated_chains(conn: sqlite3.Connection) -> list[str]:
    """Verify chain integrity for both formats.

    - Backpack: per-actor prev_event_hash chain
    - PSMC: global prev_hash chain (sequential seq numbers)
    """
    errors = []

    # --- Backpack chains (per-actor) ---
    bp_actors = [r[0] for r in conn.execute(
        "SELECT DISTINCT actor FROM events WHERE source_format = 'backpack' AND actor IS NOT NULL"
    ).fetchall()]

    for actor in bp_actors:
        rows = conn.execute(
            "SELECT event_id, prev_event_hash FROM events "
            "WHERE source_format = 'backpack' AND actor = ? "
            "ORDER BY timestamp ASC, event_id ASC",
            (actor,),
        ).fetchall()

        event_ids = {r["event_id"] for r in rows}
        for row in rows:
            prev = row["prev_event_hash"]
            if prev is not None and prev not in event_ids:
                errors.append(
                    f"[backpack] Actor '{actor}': {row['event_id']} → missing {prev}"
                )

    # --- PSMC chains (global prev_hash) ---
    psmc_rows = conn.execute(
        "SELECT event_id, hash, prev_hash, ts_logical FROM events "
        "WHERE source_format = 'psmc' ORDER BY ts_logical ASC"
    ).fetchall()

    if psmc_rows:
        hashes = {r["hash"] for r in psmc_rows if r["hash"]}
        genesis_prev = "0" * 64
        for row in psmc_rows:
            prev = row["prev_hash"]
            if prev and prev != genesis_prev and prev not in hashes:
                errors.append(
                    f"[psmc] seq={row['ts_logical']}: {row['event_id']} → missing prev_hash {prev[:16]}..."
                )

    return errors


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row to a dict with parsed payload."""
    d = dict(row)
    try:
        d["payload"] = json.loads(d.get("payload", "{}"))
    except (json.JSONDecodeError, TypeError):
        pass
    # Parse tags back to list if present
    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d
