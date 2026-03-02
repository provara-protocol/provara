# PSMC Dual-Format Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade PSMC to dual-write events to both NDJSON and SQLite using the unified schema from `migrate_ndjson.py`.

**Architecture:** On every `append_event()`, write to ndjson (source of truth) AND insert into `vault.sqlite`. Use sqlite for fast queries in `show`, `query`, and `count`. Keep verification on ndjson. Add `index` command for backfilling old vaults.

**Tech Stack:** Python 3.12, sqlite3 (stdlib), existing `provara.migrate_ndjson` module

---

### Task 1: Add SQLite initialization to `init_vault()`

**Files:**
- Modify: `tools/psmc/psmc.py:25-32` (imports)
- Modify: `tools/psmc/psmc.py:291-371` (`init_vault()`)
- Test: `tools/psmc/test_psmc.py`

**Step 1: Write the failing test**

Add to `test_psmc.py` after the existing `TestInit` class:

```python
class TestSqliteInit:
    def test_vault_sqlite_created_on_init(self, vault):
        """init_vault creates vault.sqlite with unified schema."""
        assert (vault / "vault.sqlite").exists()

    def test_vault_sqlite_has_tables(self, vault):
        import sqlite3
        conn = sqlite3.connect(str(vault / "vault.sqlite"))
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        assert "events" in tables
        assert "vault_meta" in tables
        conn.close()

    def test_vault_sqlite_wal_mode(self, vault):
        import sqlite3
        conn = sqlite3.connect(str(vault / "vault.sqlite"))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        conn.close()

    def test_vault_sqlite_empty_on_init(self, vault):
        import sqlite3
        conn = sqlite3.connect(str(vault / "vault.sqlite"))
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert count == 0
        conn.close()
```

**Step 2: Run tests to verify they fail**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py::TestSqliteInit -v`
Expected: FAIL — `vault.sqlite` doesn't exist yet

**Step 3: Implement sqlite init**

Add import at top of `psmc.py` (after line 32):
```python
import sqlite3
```

Add helper function (after `vault_path` at line ~204):
```python
# ---------------------------------------------------------------------------
# SQLite helpers (unified schema from migrate_ndjson)
# ---------------------------------------------------------------------------
_SQLITE_SCHEMA = """
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
    actor           TEXT,
    actor_key_id    TEXT,
    namespace       TEXT,
    ts_logical      INTEGER,
    prev_event_hash TEXT,
    sig             TEXT,
    raw_canonical   TEXT,
    hash            TEXT,
    prev_hash       TEXT,
    tags            TEXT,
    source_format   TEXT    NOT NULL DEFAULT 'psmc'
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor);
CREATE INDEX IF NOT EXISTS idx_events_tags ON events(tags);
CREATE INDEX IF NOT EXISTS idx_events_format ON events(source_format);
"""


def _init_vault_sqlite(vault: Path) -> sqlite3.Connection:
    """Create and initialize vault.sqlite with unified schema."""
    db_path = vault_path(vault, "vault.sqlite")
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.executescript(_SQLITE_SCHEMA)
    conn.commit()
    return conn


def _open_vault_sqlite(vault: Path) -> sqlite3.Connection | None:
    """Open vault.sqlite if it exists. Returns None if missing."""
    db_path = vault_path(vault, "vault.sqlite")
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn
```

Add to `init_vault()` function, after the `chain.ndjson` touch (line ~344):
```python
    # Create SQLite database with unified schema
    conn = _init_vault_sqlite(vault)
    conn.close()
```

**Step 4: Run tests to verify they pass**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py::TestSqliteInit -v`
Expected: 4 PASS

**Step 5: Commit**

```bash
cd ~/provara && git add tools/psmc/psmc.py tools/psmc/test_psmc.py
git commit -m "feat(psmc): add vault.sqlite creation on init with unified schema"
```

---

### Task 2: Dual-write on `append_event()`

**Files:**
- Modify: `tools/psmc/psmc.py:399-451` (`append_event()`)
- Test: `tools/psmc/test_psmc.py`

**Step 1: Write the failing test**

```python
class TestSqliteDualWrite:
    def test_append_writes_to_sqlite(self, vault):
        """append_event inserts into vault.sqlite."""
        import sqlite3
        event = psmc.append_event(vault, "note", {"title": "test note"})
        conn = sqlite3.connect(str(vault / "vault.sqlite"))
        row = conn.execute("SELECT * FROM events WHERE event_id = ?", (event["id"],)).fetchone()
        assert row is not None
        conn.close()

    def test_sqlite_event_fields(self, vault):
        """SQLite row has correct type, timestamp, payload, hash, source_format."""
        import sqlite3
        event = psmc.append_event(vault, "decision", {"title": "test"}, tags=["tag1", "tag2"])
        conn = sqlite3.connect(str(vault / "vault.sqlite"))
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute("SELECT * FROM events WHERE event_id = ?", (event["id"],)).fetchone())
        assert row["type"] == "decision"
        assert row["hash"] == event["hash"]
        assert row["prev_hash"] == event["prev_hash"]
        assert row["source_format"] == "psmc"
        assert row["ts_logical"] == event["seq"]
        assert "tag1" in row["tags"]
        conn.close()

    def test_sqlite_count_matches_ndjson(self, vault):
        """After multiple appends, sqlite count matches ndjson count."""
        import sqlite3
        for i in range(5):
            psmc.append_event(vault, "note", {"n": i})
        ndjson_count = psmc.count_events(vault)
        conn = sqlite3.connect(str(vault / "vault.sqlite"))
        sqlite_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert sqlite_count == ndjson_count == 5
        conn.close()

    def test_sqlite_payload_is_json(self, vault):
        """Payload column stores JSON-serialized data."""
        import sqlite3, json
        psmc.append_event(vault, "belief", {"confidence": 0.9, "statement": "test"})
        conn = sqlite3.connect(str(vault / "vault.sqlite"))
        row = conn.execute("SELECT payload FROM events").fetchone()
        payload = json.loads(row[0])
        assert payload["confidence"] == 0.9
        conn.close()
```

**Step 2: Run tests to verify they fail**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py::TestSqliteDualWrite -v`
Expected: FAIL — no rows in sqlite yet

**Step 3: Implement dual-write**

Add a helper function (near the other sqlite helpers):
```python
def _sqlite_insert_event(vault: Path, event: dict) -> None:
    """Insert a PSMC event into vault.sqlite."""
    conn = _open_vault_sqlite(vault)
    if conn is None:
        return  # sqlite not available, ndjson-only vault
    try:
        data = event.get("data", {})
        tags = event.get("tags", [])
        conn.execute(
            """INSERT OR IGNORE INTO events
               (event_id, type, timestamp, payload,
                actor, actor_key_id, namespace, ts_logical,
                prev_event_hash, sig, raw_canonical,
                hash, prev_hash, tags, source_format)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event["id"],
                event["type"],
                event["timestamp"],
                json.dumps(data, sort_keys=True, separators=(",", ":")),
                None,  # actor (PSMC doesn't track per-event actors)
                None,  # actor_key_id
                None,  # namespace
                event.get("seq"),  # ts_logical
                None,  # prev_event_hash (Backpack field)
                None,  # sig (Backpack field)
                None,  # raw_canonical (Backpack field)
                event.get("hash", ""),
                event.get("prev_hash"),
                json.dumps(tags) if tags else None,
                "psmc",
            ),
        )
        conn.commit()
    finally:
        conn.close()
```

Add to `append_event()`, right before the `return event` on line ~451 (after the provara emit block):
```python
    # Dual-write to SQLite
    _sqlite_insert_event(vault, event)
```

**Step 4: Run tests to verify they pass**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py::TestSqliteDualWrite -v`
Expected: 4 PASS

**Step 5: Run full test suite to check for regressions**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py -v`
Expected: All existing tests still pass

**Step 6: Commit**

```bash
cd ~/provara && git add tools/psmc/psmc.py tools/psmc/test_psmc.py
git commit -m "feat(psmc): dual-write events to ndjson and sqlite on append"
```

---

### Task 3: Use SQLite for `show_events()` and `count_events()`

**Files:**
- Modify: `tools/psmc/psmc.py:389-396` (`count_events()`)
- Modify: `tools/psmc/psmc.py:560-577` (`show_events()`)
- Test: `tools/psmc/test_psmc.py`

**Step 1: Write the failing test**

```python
class TestSqliteQueries:
    def test_count_uses_sqlite(self, vault):
        """count_events returns correct count via sqlite."""
        for i in range(3):
            psmc.append_event(vault, "note", {"n": i})
        assert psmc.count_events(vault) == 3

    def test_show_filters_by_type(self, vault, capsys):
        """show_events --type filters correctly."""
        psmc.append_event(vault, "note", {"title": "a note"})
        psmc.append_event(vault, "decision", {"title": "a decision"})
        psmc.append_event(vault, "note", {"title": "another note"})
        psmc.show_events(vault, event_type="note")
        output = capsys.readouterr().out
        assert output.count("note") == 2
        assert "decision" not in output

    def test_show_last_n(self, vault, capsys):
        """show_events --last N shows only last N events."""
        for i in range(10):
            psmc.append_event(vault, "note", {"n": i})
        psmc.show_events(vault, last_n=3)
        output = capsys.readouterr().out
        lines = [l for l in output.strip().split("\n") if l.strip()]
        assert len(lines) == 3
```

**Step 2: Run tests to verify they pass (existing behavior)**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py::TestSqliteQueries -v`
Expected: These should already pass via ndjson — we're confirming behavior parity

**Step 3: Implement sqlite-backed queries**

Replace `count_events()`:
```python
def count_events(vault: Path) -> int:
    conn = _open_vault_sqlite(vault)
    if conn is not None:
        try:
            return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        finally:
            conn.close()
    # Fallback to ndjson scanning
    events_file = vault_path(vault, "events", "events.ndjson")
    count = 0
    with open(events_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count
```

Replace `show_events()`:
```python
def show_events(vault: Path, last_n: int | None = None, event_type: str | None = None) -> None:
    conn = _open_vault_sqlite(vault)
    if conn is not None:
        try:
            clauses = []
            params: list = []
            if event_type:
                clauses.append("type = ?")
                params.append(event_type)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

            if last_n:
                # Get total matching count, then offset
                count = conn.execute(
                    f"SELECT COUNT(*) FROM events {where}", params
                ).fetchone()[0]
                offset = max(0, count - last_n)
                rows = conn.execute(
                    f"SELECT ts_logical, timestamp, type, payload FROM events {where} "
                    f"ORDER BY seq ASC LIMIT ? OFFSET ?",
                    params + [last_n, offset],
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT ts_logical, timestamp, type, payload FROM events {where} "
                    f"ORDER BY seq ASC",
                    params,
                ).fetchall()

            for row in rows:
                ts = (row[1] or "?")[:19]
                etype = row[2] or "?"
                seq = row[0] if row[0] is not None else "?"
                data_preview = row[3] or "{}"
                if len(data_preview) > 80:
                    data_preview = data_preview[:77] + "..."
                print(f"[{seq:>4}] {ts}  {etype:<12}  {data_preview}")
            return
        finally:
            conn.close()

    # Fallback to ndjson
    events = _read_ndjson(vault_path(vault, "events", "events.ndjson"))
    if event_type:
        events = [e for e in events if e.get("type") == event_type]
    if last_n:
        events = events[-last_n:]
    for e in events:
        ts = e.get("timestamp", "?")[:19]
        etype = e.get("type", "?")
        seq = e.get("seq", "?")
        data_preview = json.dumps(e.get("data", {}), ensure_ascii=False)
        if len(data_preview) > 80:
            data_preview = data_preview[:77] + "..."
        print(f"[{seq:>4}] {ts}  {etype:<12}  {data_preview}")
```

**Step 4: Run tests to verify they pass**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py::TestSqliteQueries -v`
Expected: 3 PASS

**Step 5: Run full test suite**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py -v`
Expected: All pass

**Step 6: Commit**

```bash
cd ~/provara && git add tools/psmc/psmc.py tools/psmc/test_psmc.py
git commit -m "feat(psmc): use sqlite for show and count queries with ndjson fallback"
```

---

### Task 4: Add `query_timeline()` SQLite-backed implementation

**Files:**
- Modify: `tools/psmc/psmc.py:905-929` (`query_timeline()`)
- Test: `tools/psmc/test_psmc.py`

**Step 1: Write the failing test**

```python
class TestSqliteTimeline:
    def test_query_by_type(self, vault):
        psmc.append_event(vault, "note", {"title": "n1"})
        psmc.append_event(vault, "decision", {"title": "d1"})
        results = psmc.query_timeline(vault, event_type="note")
        assert len(results) == 1
        assert results[0]["type"] == "note"

    def test_query_by_time_range(self, vault):
        from datetime import datetime, timezone, timedelta
        e1 = psmc.append_event(vault, "note", {"title": "old"})
        # All events are created "now", so query with a wide range
        results = psmc.query_timeline(
            vault,
            start_time=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            end_time=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )
        assert len(results) == 1

    def test_query_with_limit(self, vault):
        for i in range(10):
            psmc.append_event(vault, "note", {"n": i})
        results = psmc.query_timeline(vault, limit=3)
        assert len(results) == 3

    def test_query_by_tags(self, vault):
        psmc.append_event(vault, "note", {"title": "tagged"}, tags=["important", "test"])
        psmc.append_event(vault, "note", {"title": "untagged"})
        results = psmc.query_timeline(vault, tags="important")
        assert len(results) == 1
```

**Step 2: Run tests to verify baseline**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py::TestSqliteTimeline -v`

**Step 3: Implement sqlite-backed query_timeline**

Update `query_timeline()` signature to add `tags` parameter and use sqlite:

```python
def query_timeline(
    vault: Path,
    event_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: Optional[int] = None,
    tags: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Query vault events with filters. Uses sqlite if available."""
    conn = _open_vault_sqlite(vault)
    if conn is not None:
        try:
            clauses: list[str] = []
            params: list = []
            if event_type:
                clauses.append("type = ?")
                params.append(event_type)
            if start_time:
                clauses.append("timestamp >= ?")
                params.append(start_time)
            if end_time:
                clauses.append("timestamp <= ?")
                params.append(end_time)
            if tags:
                clauses.append("tags LIKE ?")
                params.append(f"%{tags}%")
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            limit_clause = f"LIMIT {limit}" if limit else ""
            rows = conn.execute(
                f"SELECT * FROM events {where} ORDER BY seq ASC {limit_clause}",
                params,
            ).fetchall()
            results = []
            for row in rows:
                d = dict(row)
                try:
                    d["data"] = json.loads(d.get("payload", "{}"))
                except (json.JSONDecodeError, TypeError):
                    d["data"] = {}
                if d.get("tags"):
                    try:
                        d["tags"] = json.loads(d["tags"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                d["id"] = d.pop("event_id", None)
                results.append(d)
            return results
        finally:
            conn.close()

    # Fallback to ndjson scanning
    events = _read_ndjson(vault_path(vault, "events", "events.ndjson"))
    if event_type:
        events = [e for e in events if e.get("type") == event_type]
    if start_time:
        start_dt = datetime.fromisoformat(start_time)
        events = [e for e in events if datetime.fromisoformat(e["timestamp"]) >= start_dt]
    if end_time:
        end_dt = datetime.fromisoformat(end_time)
        events = [e for e in events if datetime.fromisoformat(e["timestamp"]) <= end_dt]
    if limit:
        events = events[-limit:]
    return events
```

**Step 4: Run tests**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py::TestSqliteTimeline -v`
Expected: 4 PASS

**Step 5: Commit**

```bash
cd ~/provara && git add tools/psmc/psmc.py tools/psmc/test_psmc.py
git commit -m "feat(psmc): sqlite-backed query_timeline with tag filtering"
```

---

### Task 5: Add `index` CLI command (backfill existing vaults)

**Files:**
- Modify: `tools/psmc/psmc.py` (add `index_vault()` function + CLI wiring)
- Test: `tools/psmc/test_psmc.py`

**Step 1: Write the failing test**

```python
class TestSqliteIndex:
    def test_index_creates_sqlite_from_ndjson(self, tmp_path):
        """index command backfills vault.sqlite from existing ndjson-only vault."""
        # Create vault without sqlite (simulate old vault)
        v = tmp_path / "old_vault"
        psmc.init_vault(v)
        # Remove the sqlite that init now creates
        (v / "vault.sqlite").unlink()
        assert not (v / "vault.sqlite").exists()

        # Add some events (ndjson only, since sqlite is gone)
        for i in range(3):
            psmc.append_event(v, "note", {"n": i})

        # Run index
        result = psmc.index_vault(v)
        assert (v / "vault.sqlite").exists()
        assert result["count"] == 3

    def test_index_idempotent(self, vault):
        """Running index twice doesn't duplicate events."""
        import sqlite3
        psmc.append_event(vault, "note", {"title": "test"})
        psmc.index_vault(vault)
        psmc.index_vault(vault)
        conn = sqlite3.connect(str(vault / "vault.sqlite"))
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert count == 1
        conn.close()
```

**Step 2: Run tests to verify they fail**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py::TestSqliteIndex -v`
Expected: FAIL — `index_vault` doesn't exist

**Step 3: Implement `index_vault()`**

Add function:
```python
def index_vault(vault: Path) -> dict:
    """Build or rebuild vault.sqlite from events.ndjson (backfill for old vaults)."""
    events = _read_ndjson(vault_path(vault, "events", "events.ndjson"))
    conn = _init_vault_sqlite(vault)
    inserted = 0
    for event in events:
        data = event.get("data", {})
        tags = event.get("tags", [])
        try:
            conn.execute(
                """INSERT OR IGNORE INTO events
                   (event_id, type, timestamp, payload,
                    actor, actor_key_id, namespace, ts_logical,
                    prev_event_hash, sig, raw_canonical,
                    hash, prev_hash, tags, source_format)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event["id"],
                    event["type"],
                    event["timestamp"],
                    json.dumps(data, sort_keys=True, separators=(",", ":")),
                    None, None, None,
                    event.get("seq"),
                    None, None, None,
                    event.get("hash", ""),
                    event.get("prev_hash"),
                    json.dumps(tags) if tags else None,
                    "psmc",
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass
    conn.commit()
    conn.close()
    return {"count": inserted}
```

Add CLI wiring in `main()` (after `seed` parser):
```python
    # index
    sub.add_parser("index", help="Build/rebuild vault.sqlite from existing ndjson")
```

Add handler in the command dispatch (after the `seed` handler):
```python
    elif args.command == "index":
        result = index_vault(vault)
        print(f"Indexed {result['count']} events into vault.sqlite")
```

**Step 4: Run tests**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py::TestSqliteIndex -v`
Expected: 2 PASS

**Step 5: Commit**

```bash
cd ~/provara && git add tools/psmc/psmc.py tools/psmc/test_psmc.py
git commit -m "feat(psmc): add index command to backfill sqlite from existing ndjson"
```

---

### Task 6: Add `query` CLI command

**Files:**
- Modify: `tools/psmc/psmc.py` (CLI wiring for query)
- Test: `tools/psmc/test_psmc.py`

**Step 1: Write the failing test**

```python
class TestQueryCli:
    def test_query_cli_type_filter(self, vault, capsys):
        """CLI query --type filters events."""
        psmc.append_event(vault, "note", {"title": "n1"})
        psmc.append_event(vault, "decision", {"title": "d1"})
        # Simulate CLI behavior
        results = psmc.query_timeline(vault, event_type="decision")
        assert len(results) == 1
        assert results[0]["type"] == "decision"
```

**Step 2: Run test**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py::TestQueryCli -v`
Expected: Should pass (query_timeline already works)

**Step 3: Add CLI wiring**

Add parser (after `index` parser):
```python
    # query
    p_query = sub.add_parser("query", help="Query events with filters")
    p_query.add_argument("--type", dest="query_type", help="Filter by event type")
    p_query.add_argument("--since", help="Events after this ISO timestamp")
    p_query.add_argument("--until", help="Events before this ISO timestamp")
    p_query.add_argument("--tags", help="Filter by tag substring")
    p_query.add_argument("--limit", type=int, help="Max events to return")
```

Add handler:
```python
    elif args.command == "query":
        results = query_timeline(
            vault,
            event_type=args.query_type,
            start_time=args.since,
            end_time=args.until,
            tags=args.tags,
            limit=args.limit,
        )
        for e in results:
            ts = (e.get("timestamp", "?") or "?")[:19]
            etype = e.get("type", "?")
            seq = e.get("seq") or e.get("ts_logical") or "?"
            data = e.get("data") or e.get("payload", {})
            if isinstance(data, str):
                data_preview = data
            else:
                data_preview = json.dumps(data, ensure_ascii=False)
            if len(data_preview) > 80:
                data_preview = data_preview[:77] + "..."
            print(f"[{seq:>4}] {ts}  {etype:<12}  {data_preview}")
        print(f"\n{len(results)} events found.")
```

**Step 4: Run full test suite**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py -v`
Expected: All pass

**Step 5: Commit**

```bash
cd ~/provara && git add tools/psmc/psmc.py tools/psmc/test_psmc.py
git commit -m "feat(psmc): add query CLI command with type/time/tag filters"
```

---

### Task 7: Update docstring + sync_vaults sqlite rebuild + final verification

**Files:**
- Modify: `tools/psmc/psmc.py:1-23` (docstring)
- Modify: `tools/psmc/psmc.py` (`sync_vaults()`)
- Test: full suite

**Step 1: Update docstring**

Replace lines 1-23 header:
```python
#!/usr/bin/env python3
"""
Personal Sovereign Memory Container (PSMC) v1.1
================================================
A minimal, file-first, append-only event log with cryptographic integrity.
Built on Provara Protocol primitives. Designed for 20+ year durability.

Dual-format storage: NDJSON (source of truth) + SQLite (fast queries).

Cryptographic foundation: Provara SNP_Core (Ed25519 + SHA-256 + RFC 8785 canonical JSON)
Single external dependency: cryptography >= 41.0
Formats: UTF-8 NDJSON, SQLite (WAL mode), PEM keys, plain text digests
License: Apache 2.0

Usage:
    python psmc.py init
    python psmc.py append --type identity --data '{"name":"Alice"}'
    python psmc.py verify
    python psmc.py show [--last N] [--type TYPE]
    python psmc.py query --type note --since 2026-01-01
    python psmc.py index
    python psmc.py digest --weeks 1
    python psmc.py export --format markdown
    python psmc.py rotate-key
"""
```

Update VERSION constant:
```python
VERSION = "1.1.0"
```

**Step 2: Add sqlite rebuild to `sync_vaults()`**

After the `_write_ndjson` calls in `sync_vaults()` (line ~893), add:
```python
    # Rebuild sqlite index after sync
    index_vault(local_vault)
```

**Step 3: Run full test suite**

Run: `cd ~/provara && python -m pytest tools/psmc/test_psmc.py -v`
Expected: All pass

**Step 4: Run the actual agent-memory vault to verify**

Run: `python3 ~/provara/tools/psmc/psmc.py --vault ~/.provara/agent-memory show --last 3`
Expected: Shows last 3 events (using ndjson fallback since sqlite doesn't exist yet)

Run: `python3 ~/provara/tools/psmc/psmc.py --vault ~/.provara/agent-memory index`
Expected: Indexes 38 events into vault.sqlite

Run: `python3 ~/provara/tools/psmc/psmc.py --vault ~/.provara/agent-memory show --last 3`
Expected: Shows last 3 events (now via sqlite)

Run: `python3 ~/provara/tools/psmc/psmc.py --vault ~/.provara/agent-memory query --type decision`
Expected: Shows all decision events

**Step 5: Commit**

```bash
cd ~/provara && git add tools/psmc/psmc.py tools/psmc/test_psmc.py
git commit -m "feat(psmc): v1.1 — dual-format storage, query command, index backfill

PSMC now writes to both NDJSON (source of truth) and SQLite (fast queries).
Adds 'index' command for backfilling old vaults and 'query' command with
type, time range, and tag filters. All existing behavior preserved with
graceful ndjson fallback when sqlite is absent."
```
