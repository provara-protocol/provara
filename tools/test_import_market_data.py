# tools/test_import_market_data.py
import sqlite3
import json
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

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


# ---------------------------------------------------------------------------
# Task 3: yfinance tests
# ---------------------------------------------------------------------------

def _make_yf_dataframe():
    """Create a mock yfinance DataFrame (single ticker)."""
    dates = pd.to_datetime(["2026-01-01", "2026-01-02"])
    data = {
        ("Close", "SPY"): [580.0, 582.5],
        ("High", "SPY"): [581.0, 583.0],
        ("Low", "SPY"): [578.0, 580.0],
        ("Open", "SPY"): [579.0, 581.0],
        ("Volume", "SPY"): [80000000, 85000000],
    }
    df = pd.DataFrame(data, index=dates)
    df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Price", "Ticker"])
    df.index.name = "Date"
    return df


def test_import_yfinance(tmp_path):
    from import_market_data import init_db, import_yfinance
    db = tmp_path / "test.sqlite"
    conn = init_db(db)

    mock_df = _make_yf_dataframe()
    with patch("import_market_data.yf.download", return_value=mock_df):
        count = import_yfinance(conn, tickers=["SPY"], period="5d")

    assert count == 2
    rows = conn.execute(
        "SELECT * FROM events WHERE source_format='yfinance' ORDER BY timestamp"
    ).fetchall()
    assert len(rows) == 2
    payload = json.loads(rows[0]["payload"])
    assert payload["ticker"] == "SPY"
    assert payload["close"] == 580.0
    assert payload["volume"] == 80000000
    conn.close()


def test_yfinance_asset_tags(tmp_path):
    """Verify crypto, index, commodity tickers get correct tags."""
    from import_market_data import init_db, import_yfinance

    # Build a multi-ticker mock
    dates = pd.to_datetime(["2026-01-01"])
    data = {}
    for ticker in ["BTC-USD", "^VIX", "GC=F"]:
        data[("Close", ticker)] = [100.0]
        data[("High", ticker)] = [101.0]
        data[("Low", ticker)] = [99.0]
        data[("Open", ticker)] = [100.0]
        data[("Volume", ticker)] = [1000]
    df = pd.DataFrame(data, index=dates)
    df.columns = pd.MultiIndex.from_tuples(df.columns, names=["Price", "Ticker"])
    df.index.name = "Date"

    db = tmp_path / "test.sqlite"
    conn = init_db(db)
    with patch("import_market_data.yf.download", return_value=df):
        count = import_yfinance(conn, tickers=["BTC-USD", "^VIX", "GC=F"], period="5d")

    assert count == 3
    # Check tags contain correct asset types
    for row in conn.execute("SELECT * FROM events ORDER BY event_id").fetchall():
        tags = json.loads(row["tags"])
        ticker = json.loads(row["payload"])["ticker"]
        if ticker == "BTC-USD":
            assert "crypto" in tags
        elif ticker == "^VIX":
            assert "index" in tags
        elif ticker == "GC=F":
            assert "commodity" in tags
    conn.close()


# ---------------------------------------------------------------------------
# Task 4: Fear & Greed tests
# ---------------------------------------------------------------------------

MOCK_FEAR_GREED = {
    "name": "Fear and Greed Index",
    "data": [
        {"value": "25", "value_classification": "Extreme Fear", "timestamp": "1704067200"},
        {"value": "45", "value_classification": "Fear", "timestamp": "1704153600"},
        {"value": "72", "value_classification": "Greed", "timestamp": "1704240000"},
    ],
}


def test_import_fear_greed(tmp_path):
    from import_market_data import init_db, import_fear_greed
    db = tmp_path / "test.sqlite"
    conn = init_db(db)

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = MOCK_FEAR_GREED

    with patch("import_market_data.requests.get", return_value=mock_resp):
        count = import_fear_greed(conn)

    assert count == 3
    rows = conn.execute(
        "SELECT * FROM events WHERE source_format='fear_greed' ORDER BY timestamp"
    ).fetchall()
    assert len(rows) == 3
    assert rows[0]["type"] == "sentiment.extreme_fear"
    assert rows[2]["type"] == "sentiment.greed"
    payload = json.loads(rows[0]["payload"])
    assert payload["value"] == 25
    assert payload["classification"] == "Extreme Fear"
    conn.close()


# ---------------------------------------------------------------------------
# Task 5: Blockchain.com on-chain tests
# ---------------------------------------------------------------------------

MOCK_BLOCKCHAIN_CHART = {
    "name": "Hash Rate",
    "unit": "TH/s",
    "period": "day",
    "values": [
        {"x": 1704067200, "y": 520000000.0},
        {"x": 1704153600, "y": 530000000.0},
    ],
}


def test_import_blockchain_onchain(tmp_path):
    from import_market_data import init_db, import_blockchain_onchain
    db = tmp_path / "test.sqlite"
    conn = init_db(db)

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = MOCK_BLOCKCHAIN_CHART

    with patch("import_market_data.requests.get", return_value=mock_resp):
        count = import_blockchain_onchain(conn, metrics=["hash-rate"], timespan="7days")

    assert count == 2
    rows = conn.execute(
        "SELECT * FROM events WHERE source_format='blockchain_com' ORDER BY timestamp"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["type"] == "onchain.hash_rate"
    payload = json.loads(rows[0]["payload"])
    assert payload["metric"] == "hash-rate"
    assert payload["value"] == 520000000.0
    conn.close()


# ---------------------------------------------------------------------------
# Task 6: CLI tests
# ---------------------------------------------------------------------------

def test_merkle_checkpoint(tmp_path):
    from import_market_data import init_db, _insert, _merkle_checkpoint
    db = tmp_path / "test.sqlite"
    conn = init_db(db)

    # Insert some events
    for i in range(5):
        _insert(conn, f"evt-{i}", "test", f"2026-01-0{i+1}T00:00:00Z",
                {"n": i}, source="test")
    conn.commit()

    # Create checkpoint over all events (from seq 0)
    merkle = _merkle_checkpoint(conn, 0, "test_run")
    assert merkle is not None
    assert len(merkle) == 64  # SHA-256 hex

    # Verify checkpoint event was inserted
    cp = conn.execute(
        "SELECT * FROM events WHERE type='integrity.checkpoint'"
    ).fetchone()
    assert cp is not None
    payload = json.loads(cp["payload"])
    assert payload["merkle_root"] == merkle
    assert payload["event_count"] == 5
    assert payload["algorithm"] == "sha256-merkle"
    assert cp["source_format"] == "checkpoint"
    conn.close()


def test_cli_help():
    result = subprocess.run(
        ["python3", "tools/import_market_data.py", "--help"],
        capture_output=True, text=True,
        cwd="/home/syncshadow7/provara",
    )
    assert result.returncode == 0
    assert "--output" in result.stdout
    assert "--source" in result.stdout


def test_cli_unknown_source():
    """CLI with an invalid source should fail (argparse validation)."""
    result = subprocess.run(
        ["python3", "tools/import_market_data.py", "--source", "nonexistent"],
        capture_output=True, text=True,
        cwd="/home/syncshadow7/provara",
    )
    assert result.returncode != 0  # argparse rejects unknown choices
