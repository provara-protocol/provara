"""SQLite acceleration index for non-normative vault queries."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps, canonical_hash


class VaultIndex:
    """Non-normative SQLite index for fast vault queries."""

    def __init__(self, vault_path: Path):
        self.vault_path = Path(vault_path)
        self.events_path = self.vault_path / "events" / "events.ndjson"
        self.index_dir = self.vault_path / ".index"
        self.db_path = self.index_dir / "events.db"

        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                actor_key_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                prev_event_hash TEXT,
                content_hash TEXT NOT NULL,
                signature TEXT NOT NULL,
                data_json TEXT NOT NULL,
                line_offset INTEGER NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_actor ON events(actor);
            CREATE INDEX IF NOT EXISTS idx_type ON events(event_type);
            CREATE INDEX IF NOT EXISTS idx_timestamp ON events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_actor_timestamp ON events(actor, timestamp);

            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO metadata(key, value) VALUES('last_offset', '0')"
        )
        self.conn.commit()

    def _get_meta(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM metadata WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return default
        return str(row["value"])

    def _set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO metadata(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def _index_events_from_offset(self, start_offset: int) -> None:
        if not self.events_path.exists():
            self._set_meta("last_offset", "0")
            self.conn.commit()
            return

        with self.events_path.open("rb") as f:
            f.seek(start_offset)
            while True:
                offset = f.tell()
                raw = f.readline()
                if not raw:
                    break

                line = raw.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                event_id = str(event.get("event_id") or canonical_hash(event))
                event_type = str(event.get("type") or event.get("event_type") or "")
                actor = str(event.get("actor") or "")
                actor_key_id = str(event.get("actor_key_id") or "")
                timestamp = str(event.get("timestamp_utc") or event.get("timestamp") or "")
                prev_hash = event.get("prev_event_hash")
                signature = str(event.get("sig") or event.get("signature") or "")
                data_obj = event.get("data")
                if data_obj is None:
                    data_obj = event.get("payload")
                if data_obj is None:
                    data_obj = {}

                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO events(
                        event_id, event_type, actor, actor_key_id, timestamp,
                        prev_event_hash, content_hash, signature, data_json, line_offset
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        event_type,
                        actor,
                        actor_key_id,
                        timestamp,
                        str(prev_hash) if prev_hash is not None else None,
                        canonical_hash(event),
                        signature,
                        canonical_dumps(data_obj),
                        offset,
                    ),
                )

            self._set_meta("last_offset", str(f.tell()))

        self.conn.commit()

    def build(self) -> None:
        """Full rebuild from events.ndjson. Idempotent."""
        self.conn.execute("DELETE FROM events")
        self._set_meta("last_offset", "0")
        self.conn.commit()
        self._index_events_from_offset(0)

    def update(self) -> None:
        """Incremental update — index only new events since last build."""
        offset = int(self._get_meta("last_offset", "0"))
        self._index_events_from_offset(offset)

    def has_index_state(self) -> bool:
        """Whether this index has already processed at least part of the event log."""
        last_offset = int(self._get_meta("last_offset", "0"))
        row = self.conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()
        count = int(row["c"]) if row is not None else 0
        return last_offset > 0 or count > 0

    def _query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        rows = self.conn.execute(sql, params).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            data_json = str(row["data_json"])
            try:
                payload = json.loads(data_json)
            except json.JSONDecodeError:
                payload = data_json
            out.append(
                {
                    "event_id": row["event_id"],
                    "type": row["event_type"],
                    "actor": row["actor"],
                    "actor_key_id": row["actor_key_id"],
                    "timestamp_utc": row["timestamp"],
                    "prev_event_hash": row["prev_event_hash"],
                    "sig": row["signature"],
                    "payload": payload,
                    "content_hash": row["content_hash"],
                    "line_offset": row["line_offset"],
                }
            )
        return out

    def query_by_actor(self, actor: str) -> list[dict[str, Any]]:
        """All events by a specific actor."""
        return self._query(
            "SELECT * FROM events WHERE actor = ? ORDER BY line_offset ASC",
            (actor,),
        )

    def query_by_type(self, event_type: str) -> list[dict[str, Any]]:
        """All events of a specific type."""
        return self._query(
            "SELECT * FROM events WHERE event_type = ? ORDER BY line_offset ASC",
            (event_type,),
        )

    def query_by_time_range(self, start: str, end: str) -> list[dict[str, Any]]:
        """Events within ISO 8601 time range."""
        return self._query(
            "SELECT * FROM events WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC, line_offset ASC",
            (start, end),
        )

    def query_by_actor_and_time(self, actor: str, start: str, end: str) -> list[dict[str, Any]]:
        """Events by actor within time range."""
        return self._query(
            """
            SELECT * FROM events
            WHERE actor = ? AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC, line_offset ASC
            """,
            (actor, start, end),
        )

    def query_by_content(self, key: str, value: str) -> list[dict[str, Any]]:
        """Events where data contains key=value (JSON extract)."""
        json_path = f"$.{key}"
        try:
            return self._query(
                """
                SELECT * FROM events
                WHERE CAST(json_extract(data_json, ?) AS TEXT) = ?
                ORDER BY line_offset ASC
                """,
                (json_path, value),
            )
        except sqlite3.OperationalError:
            # JSON1 may be unavailable on some runtimes; fallback to Python filtering.
            rows = self._query("SELECT * FROM events ORDER BY line_offset ASC")
            return [r for r in rows if str(r.get("payload", {}).get(key)) == value]

    def get_actor_summary(self) -> dict[str, int]:
        """Event count per actor."""
        rows = self.conn.execute(
            "SELECT actor, COUNT(*) AS c FROM events GROUP BY actor ORDER BY actor ASC"
        ).fetchall()
        return {str(r["actor"]): int(r["c"]) for r in rows}

    def get_type_summary(self) -> dict[str, int]:
        """Event count per event type."""
        rows = self.conn.execute(
            "SELECT event_type, COUNT(*) AS c FROM events GROUP BY event_type ORDER BY event_type ASC"
        ).fetchall()
        return {str(r["event_type"]): int(r["c"]) for r in rows}

    def get_chain_heads(self) -> dict[str, str]:
        """Latest event hash per actor chain."""
        rows = self.conn.execute(
            """
            SELECT e.actor, e.event_id
            FROM events e
            INNER JOIN (
                SELECT actor, MAX(line_offset) AS max_offset
                FROM events
                GROUP BY actor
            ) latest ON latest.actor = e.actor AND latest.max_offset = e.line_offset
            ORDER BY e.actor ASC
            """
        ).fetchall()
        return {str(r["actor"]): str(r["event_id"]) for r in rows}

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "VaultIndex":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
