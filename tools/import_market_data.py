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

import pandas as pd
import requests
import yfinance as yf

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
            if not isinstance(payload, str) else payload,
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


# ---------------------------------------------------------------------------
# yfinance — Equities, Crypto, Commodities
# ---------------------------------------------------------------------------

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
        df.columns = pd.MultiIndex.from_product(
            [df.columns, available_tickers], names=["Price", "Ticker"]
        )

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


# ---------------------------------------------------------------------------
# Alternative.me — Crypto Fear & Greed Index
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Blockchain.com — Bitcoin On-Chain Metrics
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

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
