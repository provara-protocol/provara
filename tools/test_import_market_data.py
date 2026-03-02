# tools/test_import_market_data.py
import sqlite3
import json
import pytest
from pathlib import Path

# Allow importing from tools/
import sys
sys.path.insert(0, str(Path(__file__).parent))

def test_init_db_creates_schema(tmp_path):
    from import_market_data import init_db
    db = tmp_path / "test.sqlite"
    conn = init_db(db)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {r[0] for r in tables}
    assert "events" in table_names
    assert "vault_meta" in table_names
    conn.close()

def test_insert_and_get_last_timestamp(tmp_path):
    from import_market_data import init_db, _insert, _get_last_timestamp
    db = tmp_path / "test.sqlite"
    conn = init_db(db)
    _insert(conn, "test-1", "price.ohlcv", "2026-01-01T00:00:00Z",
            {"close": 100}, tags=["btc"], source="test")
    _insert(conn, "test-2", "price.ohlcv", "2026-01-02T00:00:00Z",
            {"close": 200}, tags=["btc"], source="test")
    conn.commit()
    last = _get_last_timestamp(conn, "price.ohlcv", "test")
    assert last == "2026-01-02T00:00:00Z"
    conn.close()

def test_insert_dedup(tmp_path):
    from import_market_data import init_db, _insert
    db = tmp_path / "test.sqlite"
    conn = init_db(db)
    r1 = _insert(conn, "dup-1", "test", "2026-01-01T00:00:00Z", {}, source="test")
    conn.commit()
    r2 = _insert(conn, "dup-1", "test", "2026-01-01T00:00:00Z", {}, source="test")
    assert r1 is True
    assert r2 is False
    count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    assert count == 1
    conn.close()
