# tools/test_import_market_data.py
import sqlite3
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

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


MOCK_COINGECKO_OHLC = [
    [1704067200000, 42000.0, 42500.0, 41800.0, 42200.0],  # 2024-01-01
    [1704153600000, 42200.0, 43000.0, 42100.0, 42800.0],  # 2024-01-02
]

def test_import_coingecko_ohlc(tmp_path):
    from import_market_data import init_db, import_coingecko_ohlc
    db = tmp_path / "test.sqlite"
    conn = init_db(db)

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_COINGECKO_OHLC

    with patch("import_market_data.requests.get", return_value=mock_resp):
        count = import_coingecko_ohlc(conn, coins=["bitcoin"], days=7)

    assert count == 2
    rows = conn.execute(
        "SELECT * FROM events WHERE source_format='coingecko' ORDER BY timestamp"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["type"] == "price.ohlcv"
    payload = json.loads(rows[0]["payload"])
    assert payload["coin"] == "bitcoin"
    assert payload["close"] == 42200.0
    conn.close()

def test_coingecko_dedup(tmp_path):
    from import_market_data import init_db, import_coingecko_ohlc
    db = tmp_path / "test.sqlite"
    conn = init_db(db)

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_COINGECKO_OHLC

    with patch("import_market_data.requests.get", return_value=mock_resp):
        c1 = import_coingecko_ohlc(conn, coins=["bitcoin"], days=7)
        c2 = import_coingecko_ohlc(conn, coins=["bitcoin"], days=7)

    assert c1 == 2
    assert c2 == 0  # all dupes skipped
    conn.close()
