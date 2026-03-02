#!/usr/bin/env python3
"""
import_market_data.py — Fetch live market data from free APIs into Provara vault.

Sources (all zero-auth or already-installed):
  - CoinGecko: Crypto OHLC (BTC, ETH, SOL)
  - yfinance:  Equities + crypto + commodities OHLCV
  - Alternative.me: Crypto Fear & Greed Index
  - Blockchain.com: Bitcoin on-chain metrics

Usage:
    python tools/import_market_data.py --output ~/master-vault/vault.sqlite
    python tools/import_market_data.py --output ~/master-vault/vault.sqlite --source fear_greed
    python tools/import_market_data.py --output ~/master-vault/vault.sqlite --backfill
"""

import json
import sqlite3
import time
import os
from pathlib import Path

SCHEMA_SQL = """
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
    source_format   TEXT    NOT NULL DEFAULT 'imported'
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor);
CREATE INDEX IF NOT EXISTS idx_events_tags ON events(tags);
CREATE INDEX IF NOT EXISTS idx_events_format ON events(source_format);
"""


def init_db(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def _insert(conn, event_id, etype, ts, payload, tags=None, source="imported", actor=None):
    cur = conn.execute(
        """INSERT OR IGNORE INTO events
           (event_id, type, timestamp, payload, tags, source_format, actor)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            str(event_id),
            etype,
            ts,
            json.dumps(payload, sort_keys=True, separators=(",", ":"))
            if isinstance(payload, dict) else payload,
            json.dumps(tags) if tags else None,
            source,
            actor,
        ),
    )
    return cur.rowcount > 0


def _get_last_timestamp(conn, event_type, source):
    """Get the most recent timestamp for a given type+source (for incremental imports)."""
    row = conn.execute(
        "SELECT MAX(timestamp) FROM events WHERE type = ? AND source_format = ?",
        (event_type, source),
    ).fetchone()
    return row[0] if row and row[0] else None
