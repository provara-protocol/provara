# Market Data Importers Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build live market data importers that fetch crypto, equities, macro sentiment, and on-chain metrics from free APIs into master-vault/vault.sqlite.

**Architecture:** A single `import_market_data.py` tool in `provara/tools/` that follows the existing `import_datasets.py` pattern — one function per data source, shared `_insert` helper, unified schema. Each importer supports incremental mode (skip data already in vault) and full backfill mode. Zero-auth APIs only (Binance is geo-blocked from US).

**Tech Stack:** Python 3.12, requests, yfinance, sqlite3 (all already installed)

**Verified API Endpoints:**
- CoinGecko OHLC: `GET /api/v3/coins/{id}/ohlc` — free, no key, 30 req/min
- yfinance: `yf.download()` — crypto (BTC-USD) + equities (SPY) + commodities (GC=F)
- Alternative.me: `GET /fng/?limit=N` — full history since 2018, no auth
- Blockchain.com Charts: `GET /charts/{metric}?timespan=Xdays&format=json` — no auth, all metrics verified

**Target vault:** `~/master-vault/vault.sqlite` (currently 20,892 events)

---

### Task 1: Core Scaffold + Tests

**Files:**
- Create: `tools/import_market_data.py`
- Create: `tools/test_import_market_data.py`

**Step 1: Write failing test for scaffold**

```python
# tools/test_import_market_data.py
import sqlite3
import pytest
from pathlib import Path

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
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/syncshadow7/provara && python -m pytest tools/test_import_market_data.py -v`
Expected: FAIL (import_market_data not found)

**Step 3: Write minimal scaffold**

```python
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
    try:
        conn.execute(
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
        return True
    except sqlite3.IntegrityError:
        return False


def _get_last_timestamp(conn, event_type, source):
    """Get the most recent timestamp for a given type+source (for incremental imports)."""
    row = conn.execute(
        "SELECT MAX(timestamp) FROM events WHERE type = ? AND source_format = ?",
        (event_type, source),
    ).fetchone()
    return row[0] if row and row[0] else None
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/syncshadow7/provara && python -m pytest tools/test_import_market_data.py -v`
Expected: 3 passed

**Step 5: Commit**

```bash
cd /home/syncshadow7/provara
git add tools/import_market_data.py tools/test_import_market_data.py
git commit -m "feat: scaffold market data importer with core helpers"
```

---

### Task 2: CoinGecko Crypto OHLC Importer

**Files:**
- Modify: `tools/import_market_data.py`
- Modify: `tools/test_import_market_data.py`

**Context:** CoinGecko `/api/v3/coins/{id}/ohlc?vs_currency=usd&days=N` returns `[[timestamp_ms, open, high, low, close], ...]`. Free tier: 30 req/min, no key needed. days=1|7|14|30|90|180|365|max. Candle granularity: 1-2 days→30min, 3-30→4hr, 31+→4days.

**Step 1: Write failing test**

```python
# Add to test_import_market_data.py
from unittest.mock import patch, MagicMock

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
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/syncshadow7/provara && python -m pytest tools/test_import_market_data.py::test_import_coingecko_ohlc -v`
Expected: FAIL (import_coingecko_ohlc not found)

**Step 3: Write implementation**

```python
# Add to import_market_data.py after _get_last_timestamp

import requests

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
DEFAULT_COINS = ["bitcoin", "ethereum", "solana"]

def import_coingecko_ohlc(conn, coins=None, days=90):
    """Import crypto OHLC from CoinGecko. Returns count of new events."""
    coins = coins or DEFAULT_COINS
    total = 0

    for coin in coins:
        time.sleep(2.1)  # respect 30 req/min rate limit
        resp = requests.get(
            f"{COINGECKO_BASE}/coins/{coin}/ohlc",
            params={"vs_currency": "usd", "days": days},
            timeout=30,
        )
        if not resp.ok:
            print(f"  WARN  CoinGecko {coin}: HTTP {resp.status_code}")
            continue

        candles = resp.json()
        for candle in candles:
            ts_ms, o, h, l, c = candle
            ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts_ms / 1000))
            event_id = f"cg-{coin}-{ts_ms}"

            payload = {
                "coin": coin,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "vs_currency": "usd",
            }

            if _insert(conn, event_id, "price.ohlcv", ts, payload,
                       tags=["crypto", coin, "ohlc"], source="coingecko"):
                total += 1

        conn.commit()

    return total
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/syncshadow7/provara && python -m pytest tools/test_import_market_data.py -v`
Expected: 5 passed

**Step 5: Commit**

```bash
cd /home/syncshadow7/provara
git add tools/import_market_data.py tools/test_import_market_data.py
git commit -m "feat: add CoinGecko crypto OHLC importer"
```

---

### Task 3: yfinance Equities + Commodities Importer

**Files:**
- Modify: `tools/import_market_data.py`
- Modify: `tools/test_import_market_data.py`

**Context:** `yfinance` is installed (v1.2.0). `yf.download(tickers, period, progress=False)` returns pandas DataFrame with columns: Open, High, Low, Close, Volume. Multi-level columns when multi-ticker: `(Price, Ticker)`. Supports tickers like SPY, QQQ, BTC-USD, ETH-USD, GC=F (gold), CL=F (oil), ^VIX.

**Step 1: Write failing test**

```python
# Add to test_import_market_data.py
import pandas as pd

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
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/syncshadow7/provara && python -m pytest tools/test_import_market_data.py::test_import_yfinance -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# Add to import_market_data.py
import yfinance as yf

DEFAULT_TICKERS = ["SPY", "QQQ", "BTC-USD", "ETH-USD", "GC=F", "^VIX"]

def import_yfinance(conn, tickers=None, period="1y"):
    """Import OHLCV from Yahoo Finance. Returns count of new events."""
    tickers = tickers or DEFAULT_TICKERS
    total = 0

    df = yf.download(tickers, period=period, progress=False)
    if df.empty:
        return 0

    # Handle both single and multi-ticker DataFrames
    if isinstance(df.columns, pd.MultiIndex):
        available_tickers = df.columns.get_level_values("Ticker").unique().tolist()
    else:
        # Single ticker — wrap into multi-level for uniform processing
        available_tickers = tickers[:1]
        df.columns = pd.MultiIndex.from_product([df.columns, available_tickers],
                                                 names=["Price", "Ticker"])

    for ticker in available_tickers:
        try:
            sub = df.xs(ticker, level="Ticker", axis=1)
        except KeyError:
            continue

        for date, row in sub.iterrows():
            ts = date.strftime("%Y-%m-%dT16:00:00Z")
            event_id = f"yf-{ticker}-{date.strftime('%Y%m%d')}"

            close = row.get("Close")
            if pd.isna(close):
                continue

            payload = {
                "ticker": ticker,
                "open": round(float(row.get("Open", 0)), 4),
                "high": round(float(row.get("High", 0)), 4),
                "low": round(float(row.get("Low", 0)), 4),
                "close": round(float(close), 4),
                "volume": int(row.get("Volume", 0)),
            }

            # Classify asset type from ticker
            if ticker.endswith("-USD"):
                asset_tags = ["crypto", ticker.split("-")[0].lower()]
            elif ticker.startswith("^"):
                asset_tags = ["index", ticker.lower()]
            elif "=" in ticker:
                asset_tags = ["commodity", ticker.split("=")[0].lower()]
            else:
                asset_tags = ["equity", ticker.lower()]

            if _insert(conn, event_id, "price.ohlcv", ts, payload,
                       tags=["ohlcv"] + asset_tags, source="yfinance"):
                total += 1

        conn.commit()

    return total
```

**Step 4: Run tests**

Run: `cd /home/syncshadow7/provara && python -m pytest tools/test_import_market_data.py -v`
Expected: 6 passed

**Step 5: Commit**

```bash
cd /home/syncshadow7/provara
git add tools/import_market_data.py tools/test_import_market_data.py
git commit -m "feat: add yfinance equities/crypto/commodity importer"
```

---

### Task 4: Alternative.me Fear & Greed Index Importer

**Files:**
- Modify: `tools/import_market_data.py`
- Modify: `tools/test_import_market_data.py`

**Context:** `GET https://api.alternative.me/fng/?limit=N&format=json` returns `{"data": [{"value": "10", "value_classification": "Extreme Fear", "timestamp": "1772409600"}, ...]}`. No auth. `limit=0` returns full history (since Feb 2018). Timestamp is Unix seconds.

**Step 1: Write failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd /home/syncshadow7/provara && python -m pytest tools/test_import_market_data.py::test_import_fear_greed -v`
Expected: FAIL

**Step 3: Write implementation**

```python
FEAR_GREED_URL = "https://api.alternative.me/fng/"

def import_fear_greed(conn, limit=0):
    """Import Crypto Fear & Greed Index. limit=0 means full history."""
    resp = requests.get(FEAR_GREED_URL, params={"limit": limit, "format": "json"}, timeout=30)
    if not resp.ok:
        print(f"  WARN  Fear & Greed: HTTP {resp.status_code}")
        return 0

    data = resp.json().get("data", [])
    total = 0

    for entry in data:
        value = int(entry["value"])
        ts_unix = int(entry["timestamp"])
        ts = time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime(ts_unix))
        event_id = f"fng-{ts_unix}"

        classification = entry.get("value_classification", "")

        # Map to semantic event type
        if value <= 25:
            etype = "sentiment.extreme_fear"
        elif value <= 45:
            etype = "sentiment.fear"
        elif value <= 55:
            etype = "sentiment.neutral"
        elif value <= 75:
            etype = "sentiment.greed"
        else:
            etype = "sentiment.extreme_greed"

        payload = {
            "value": value,
            "classification": classification,
            "index": "crypto_fear_greed",
        }

        if _insert(conn, event_id, etype, ts, payload,
                   tags=["sentiment", "crypto", "fear-greed"], source="fear_greed"):
            total += 1

    conn.commit()
    return total
```

**Step 4: Run tests**

Run: `cd /home/syncshadow7/provara && python -m pytest tools/test_import_market_data.py -v`
Expected: 7 passed

**Step 5: Commit**

```bash
cd /home/syncshadow7/provara
git add tools/import_market_data.py tools/test_import_market_data.py
git commit -m "feat: add Fear & Greed Index importer"
```

---

### Task 5: Blockchain.com On-Chain Metrics Importer

**Files:**
- Modify: `tools/import_market_data.py`
- Modify: `tools/test_import_market_data.py`

**Context:** `GET https://api.blockchain.info/charts/{metric}?timespan={N}days&format=json` returns `{"name": "...", "values": [{"x": unix_ts, "y": float_value}, ...]}`. No auth. Available metrics verified: `hash-rate`, `n-transactions`, `mempool-size`, `n-unique-addresses`, `market-price`, `total-bitcoins`.

**Step 1: Write failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd /home/syncshadow7/provara && python -m pytest tools/test_import_market_data.py::test_import_blockchain_onchain -v`
Expected: FAIL

**Step 3: Write implementation**

```python
BLOCKCHAIN_CHARTS_URL = "https://api.blockchain.info/charts"
DEFAULT_ONCHAIN_METRICS = [
    "hash-rate",
    "n-transactions",
    "n-unique-addresses",
    "mempool-size",
    "market-price",
]

def import_blockchain_onchain(conn, metrics=None, timespan="1year"):
    """Import BTC on-chain metrics from Blockchain.com. Returns count of new events."""
    metrics = metrics or DEFAULT_ONCHAIN_METRICS
    total = 0

    for metric in metrics:
        resp = requests.get(
            f"{BLOCKCHAIN_CHARTS_URL}/{metric}",
            params={"timespan": timespan, "format": "json"},
            timeout=30,
        )
        if not resp.ok:
            print(f"  WARN  Blockchain.com {metric}: HTTP {resp.status_code}")
            continue

        data = resp.json()
        values = data.get("values", [])
        etype = f"onchain.{metric.replace('-', '_')}"

        for point in values:
            ts_unix = point["x"]
            value = point["y"]
            ts = time.strftime("%Y-%m-%dT00:00:00Z", time.gmtime(ts_unix))
            event_id = f"bc-{metric}-{ts_unix}"

            payload = {
                "metric": metric,
                "value": value,
                "unit": data.get("unit", ""),
                "name": data.get("name", ""),
            }

            if _insert(conn, event_id, etype, ts, payload,
                       tags=["bitcoin", "onchain", metric], source="blockchain_com"):
                total += 1

        conn.commit()
        time.sleep(0.5)  # be polite

    return total
```

**Step 4: Run tests**

Run: `cd /home/syncshadow7/provara && python -m pytest tools/test_import_market_data.py -v`
Expected: 8 passed

**Step 5: Commit**

```bash
cd /home/syncshadow7/provara
git add tools/import_market_data.py tools/test_import_market_data.py
git commit -m "feat: add Blockchain.com on-chain metrics importer"
```

---

### Task 6: CLI Main + Integration

**Files:**
- Modify: `tools/import_market_data.py`
- Modify: `tools/test_import_market_data.py`

**Context:** Wire up argparse CLI so the tool can be run standalone. Support `--output` (default ~/master-vault/vault.sqlite), `--source` (specific source or "all"), `--backfill` flag for full history.

**Step 1: Write failing test**

```python
import subprocess

def test_cli_help():
    result = subprocess.run(
        ["python3", "tools/import_market_data.py", "--help"],
        capture_output=True, text=True,
        cwd="/home/syncshadow7/provara",
    )
    assert result.returncode == 0
    assert "--output" in result.stdout
    assert "--source" in result.stdout

def test_cli_dry_run(tmp_path):
    """Test CLI with a source that uses mocked data via --dry-run."""
    from import_market_data import init_db
    db = tmp_path / "test.sqlite"
    init_db(db).close()
    # Just verify the CLI entrypoint doesn't crash with unknown source
    result = subprocess.run(
        ["python3", "tools/import_market_data.py",
         "--output", str(db), "--source", "nonexistent"],
        capture_output=True, text=True,
        cwd="/home/syncshadow7/provara",
    )
    # Should complete without crash (unknown source is skipped)
    assert result.returncode == 0
```

**Step 2: Run tests to verify they fail**

Run: `cd /home/syncshadow7/provara && python -m pytest tools/test_import_market_data.py::test_cli_help -v`
Expected: FAIL

**Step 3: Write implementation**

```python
# Add to import_market_data.py at the bottom

import pandas as pd  # needed at module level for yfinance DataFrame handling

IMPORTERS = {
    "coingecko": ("CoinGecko Crypto OHLC", lambda conn, bf: import_coingecko_ohlc(conn, days=365 if bf else 30)),
    "yfinance": ("Yahoo Finance OHLCV", lambda conn, bf: import_yfinance(conn, period="max" if bf else "1y")),
    "fear_greed": ("Crypto Fear & Greed Index", lambda conn, bf: import_fear_greed(conn, limit=0)),
    "blockchain": ("Blockchain.com On-Chain", lambda conn, bf: import_blockchain_onchain(conn, timespan="all" if bf else "1year")),
}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import live market data into Provara vault")
    parser.add_argument("--output", "-o", default=os.path.expanduser("~/master-vault/vault.sqlite"))
    parser.add_argument("--source", "-s", default="all",
                        choices=list(IMPORTERS.keys()) + ["all"],
                        help="Which data source to import (default: all)")
    parser.add_argument("--backfill", action="store_true",
                        help="Fetch maximum history (slower, more API calls)")
    args = parser.parse_args()

    conn = init_db(args.output)
    before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    print(f"Importing market data into {args.output}\n")

    sources = IMPORTERS if args.source == "all" else {args.source: IMPORTERS[args.source]}
    grand_total = 0

    for key, (name, importer_fn) in sources.items():
        t0 = time.time()
        try:
            count = importer_fn(conn, args.backfill)
            elapsed = time.time() - t0
            print(f"  OK    {name}: {count:,} new events ({elapsed:.1f}s)")
            grand_total += count
        except Exception as e:
            print(f"  FAIL  {name}: {e}")

    after = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    print(f"\n{'='*50}")
    print(f"New events: {grand_total:,}")
    print(f"Vault total: {after:,} (was {before:,})")

    size = os.path.getsize(args.output)
    print(f"Vault size: {size/1024/1024:.1f} MB")

    conn.close()


if __name__ == "__main__":
    main()
```

**Step 4: Run tests**

Run: `cd /home/syncshadow7/provara && python -m pytest tools/test_import_market_data.py -v`
Expected: 10 passed

**Step 5: Commit**

```bash
cd /home/syncshadow7/provara
git add tools/import_market_data.py tools/test_import_market_data.py
git commit -m "feat: add CLI main with source selection and backfill mode"
```

---

### Task 7: Live Smoke Test

**Files:**
- No file changes — verification only

**Step 1: Run Fear & Greed importer against master vault (fastest, safest)**

Run: `cd /home/syncshadow7/provara && python tools/import_market_data.py --output ~/master-vault/vault.sqlite --source fear_greed`

Expected: Imports ~2,500+ events (full history since Feb 2018), no errors.

**Step 2: Run Blockchain.com on-chain importer**

Run: `cd /home/syncshadow7/provara && python tools/import_market_data.py --output ~/master-vault/vault.sqlite --source blockchain`

Expected: Imports ~1,800+ events (5 metrics × 365 days), no errors.

**Step 3: Run yfinance importer**

Run: `cd /home/syncshadow7/provara && python tools/import_market_data.py --output ~/master-vault/vault.sqlite --source yfinance`

Expected: Imports ~1,500+ events (6 tickers × 252 trading days), no errors.

**Step 4: Run CoinGecko importer (slowest due to rate limit)**

Run: `cd /home/syncshadow7/provara && python tools/import_market_data.py --output ~/master-vault/vault.sqlite --source coingecko`

Expected: Imports ~90+ events (3 coins × 30 days), no errors.

**Step 5: Verify vault totals**

Run: `python3 -c "import sqlite3; conn = sqlite3.connect(os.path.expanduser('~/master-vault/vault.sqlite')); ..."`

Verify new source formats appear and total event count grew.

**Step 6: Commit verified state**

No code changes needed — this is a verification-only task.
