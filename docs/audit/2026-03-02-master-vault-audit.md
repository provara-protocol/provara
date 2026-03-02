# Master Vault Systems Audit Report

**Date:** 2026-03-02
**Auditor:** Claude Code (The Architect)
**Scope:** All Provara + Kestrel data stores
**Vault:** `/home/syncshadow7/master-vault/vault.sqlite` (29,093 events, 13.2 MB)

---

## Phase 1 — Locate the Truth

### 1.1 SQLite File Inventory

| # | Path | Size | Rows | Status |
|---|------|------|------|--------|
| 1 | `~/master-vault/vault.sqlite` | **13.2 MB** | **29,093** | **ACTIVE PRIMARY** |
| 2 | `~/provara/master-vault/vault.sqlite` | 10.0 MB | 20,886 | STALE COPY (-8,207) |
| 3 | `~/provara/sites/provara.dev/observatory/vault.sqlite` | 10.0 MB | 20,886 | STALE COPY |
| 4 | `~/provara/sites/provara-dev/observatory/vault.sqlite` | 10.0 MB | 20,886 | STALE COPY |
| 5 | `~/.provara/agent-memory/vault.sqlite` | 188 KB | 41 | ACTIVE (PSMC agent memory) |
| 6 | `~/provara/master-vault/identity/privacy_keys.db` | 20 KB | 0 | EMPTY (schema only) |
| 7-10 | `~/provara/master-vault/legacy_intel/kestrel/*.db` | 16-60 KB | 0 | EMPTY (copied from Kestrel) |
| 11-17 | `~/kestrel/*.db` (7 files across 3 dirs) | 16-112 KB | 0 | EMPTY (all Kestrel DBs) |

**Finding:** 3 stale vault copies exist at 20,886 rows (pre-market-import snapshot). Active vault is at 29,093. All 7 Kestrel databases are empty schema-only.

### 1.2 NDJSON File Inventory

| # | Path | Size | Lines | Status |
|---|------|------|-------|--------|
| 1 | `~/.provara/agent-memory/events/events.ndjson` | 69 KB | 43 | ACTIVE (source of truth) |
| 2 | `~/.provara/agent-memory/chain/chain.ndjson` | 14 KB | 41 | ACTIVE (hash chain) |
| 3 | `~/master-vault/events/events.ndjson` | 938 B | 2 | GENESIS + 1 event |
| 4 | `~/provara/master-vault/events/events.ndjson` | 938 B | 2 | Copy of #3 |
| 5 | `~/provara/Examples/Demo_Backpack/events/events.ndjson` | 2.3 KB | 5 | Demo fixture |
| 6 | `~/provara/tests/fixtures/reference_backpack/events/events.ndjson` | 940 B | 2 | Test fixture |

**Finding:** Only `~/.provara/agent-memory/` has substantive NDJSON data (43 events). The master-vault NDJSON has only 2 events — the SQLite is the real data store.

### 1.3 Active Schema (Vault Events Table)

```sql
CREATE TABLE events (
    seq              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id         TEXT NOT NULL UNIQUE,
    type             TEXT NOT NULL,
    timestamp        TEXT NOT NULL,
    payload          TEXT NOT NULL,        -- JSON blob
    actor            TEXT,
    actor_key_id     TEXT,
    namespace        TEXT,
    ts_logical       INTEGER,
    prev_event_hash  TEXT,
    sig              TEXT,
    raw_canonical    TEXT,
    hash             TEXT,
    prev_hash        TEXT,
    tags             TEXT,                 -- JSON array
    source_format    TEXT NOT NULL DEFAULT 'imported'
);
-- Indexes: type, timestamp, actor, tags, source_format
```

### 1.4 Write Paths (Code That Mutates Data)

**SQLite writers:** 10 distinct files
- `src/provara/storage_sqlite.py:174` — primary vault engine INSERT
- `tools/psmc/psmc.py:214-263` — PSMC dual-format INSERT
- `tools/import_market_data.py:70` — market data INSERT
- `tools/import_datasets.py:72` — dataset INSERT
- `tools/seed_vault.py:78` — seed vault INSERT
- `src/provara/query.py:69`, `privacy.py:43`, `crypto_shred.py:58`, `migrate_ndjson.py:290`

**NDJSON append writers:** 11 distinct files
- `src/provara/__init__.py:173`, `cli.py:671`, `oracle.py:106`, `archival.py:88`, `migrate.py:164`, `rekey_backpack.py:139`, `market.py:121`, `scitt.py:213`, `timestamp.py:148`
- `tools/psmc/psmc.py:572` — PSMC events + chain append
- `tools/benchmarks/benchmark.py:133`

---

## Phase 2 — Sanity Audit

### 2.1 Time Coverage

| Source | Events | Min Timestamp | Max Timestamp | Cadence |
|--------|--------|---------------|---------------|---------|
| treasury | 8,756 | 1990-01-02 | 2024-12-31 | daily (business days) |
| worldbank | 4,846 | 2000-06-30 | 2024-06-30 | yearly (per country) |
| blockchain_com | 2,976 | 2025-03-02 | 2026-03-02 | daily (5 metrics/day) |
| fear_greed | 2,948 | 2018-02-01 | 2026-03-02 | daily |
| synthetic | 1,958 | 2025-03-07 | 2026-03-01 | hourly (2h median) |
| mitre_attack | 1,861 | 2017-05-31 | 2025-10-22 | event-based |
| yfinance | 1,737 | 2025-03-02 | 2026-03-02 | daily (6 tickers/day) |
| gdelt | 1,639 | 2025-03-02 | 2026-03-02 | event-based (batch) |
| cisa_kev | 1,529 | 2021-11-03 | 2026-02-25 | event-based |
| coingecko | 540 | 2026-02-01 | 2026-03-02 | sub-daily (3 coins) |
| usgs | 262 | 2026-03-01 | 2026-03-02 | event-based |
| psmc | 39 | 2026-03-01 | 2026-03-02 | event-based |
| backpack | 2 | 2026-03-01 | 2026-03-01 | event-based |

**Gap analysis (daily sources):**
- **treasury:** 275 gaps >3 days — all weekends/federal holidays. Expected for business-day data.
- **blockchain_com:** No gaps >3 days. Clean.
- **coingecko:** No gaps >3 days. Clean.
- **fear_greed:** 1 gap: `2018-04-13 -> 2018-04-17` (4 days). API data gap near series start. Minor.
- **yfinance:** No gaps >3 days. Clean.

### 2.2 Duplicate Detection

**Event ID collisions: 0.** Every `event_id` is unique. UNIQUE constraint enforced.

**Semantic duplicates (source + type + timestamp):** 20 groups found. None are true duplicates:

| Pattern | Count | Explanation |
|---------|-------|-------------|
| gdelt/geopolitical.event/2026-03-02 | 1,199 | Multi-event batch (different actors/countries) |
| cisa_kev/cve.exploited/2021-11-03 | 287 | Catalog launch date (287 CVEs added day 1) |
| worldbank/economic.gdp/2009-06-30 | 196 | One row per country per year |
| gdelt/geopolitical.conflict/2026-03-02 | 268 | Multi-event batch |

**Verdict:** No actual data corruption. Multi-entity records sharing timestamps by design.

### 2.3 Schema Drift (Payload Field Consistency)

**Clean sources (100% field consistency across 100 sampled events):**

| Source | Fields | Status |
|--------|--------|--------|
| blockchain_com | metric, name, unit, value | CLEAN |
| cisa_kev | action, cve_id, description, due_date, known_ransomware, name, product, vendor | CLEAN |
| coingecko | close, coin, high, low, open, vs_currency | CLEAN |
| fear_greed | classification, index, value | CLEAN |
| gdelt | actor1, actor2, country, event_code, goldstein_scale, num_mentions | CLEAN |
| mitre_attack | attack_id, description, kill_chain_phases, name, object_type, platforms | CLEAN |
| treasury | date, spread_2_10, yields | CLEAN |
| usgs | 10 fields | CLEAN |
| worldbank | 6 fields | CLEAN |
| yfinance | close, high, low, open, ticker, volume | CLEAN |

**Intentionally heterogeneous sources:**

| Source | Notes |
|--------|-------|
| psmc (39) | Mixed event types by design (decisions, notes, milestones — each has different fields) |
| synthetic (1,958) | Test data with varied schemas |
| backpack (2) | Only 2 events with different schemas |

### 2.4 Null Rate Per Column

| Column | Null Count | Rate | Assessment |
|--------|-----------|------|------------|
| event_id | 0 | 0.0% | CLEAN |
| type | 0 | 0.0% | CLEAN |
| timestamp | 0 | 0.0% | CLEAN |
| payload | 0 | 0.0% | CLEAN |
| source_format | 0 | 0.0% | CLEAN |
| tags | 4 | 0.0% | CLEAN |
| **actor** | **27,133** | **93.3%** | Only psmc + synthetic populate this |
| **hash** | **27,096** | **93.1%** | Only psmc + synthetic are hash-chained |
| **prev_hash** | **27,096** | **93.1%** | Same as hash |
| **sig** | **29,091** | **99.99%** | Only 2 backpack events are signed |

**STRUCTURAL RISK:** The vault schema supports cryptographic integrity (hash chains, signatures) but 93% of events lack both. The tamper-evidence chain covers only PSMC + synthetic data (~7% of vault).

### 2.5 Unit Inconsistency

| Data Source | Field | Sample Values | Unit | Status |
|-------------|-------|---------------|------|--------|
| treasury | yields | 4.16 - 4.86 | percent | CORRECT |
| yfinance | close | $86,065 - $94,248 (BTC-USD) | USD | CORRECT |
| coingecko | close | $78,380 - $78,770 | USD | CORRECT |
| yfinance | close | $580 - $686 (SPY) | USD | CORRECT |
| yfinance | volume | 80M - 85M | shares | CORRECT |
| fear_greed | value | 10 - 72 | index (0-100) | CORRECT |
| blockchain_com | hash_rate value | 692M - 1.07B | TH/s | **WARNING** |
| blockchain_com | mempool_size value | 3.7M - 108M | bytes | CORRECT |
| worldbank | value_usd | 1.4T - 29T | USD | CORRECT |
| gdelt | goldstein_scale | -10 to +10 | Goldstein scale | CORRECT |

**WARNING: Blockchain.com `hash-rate` unit label is "TH/s" but values are in the hundreds of millions.** 692,000,000 TH/s = 692 EH/s. The raw value is technically correct (Bitcoin's hashrate expressed in TH/s), but the magnitude is misleading. Downstream consumers expecting small TH/s numbers will miscalculate.

### 2.6 Cadence / Joinability

| Source | True Cadence | Records Per Date | Join Strategy |
|--------|-------------|-----------------|---------------|
| treasury | business-day | 1 | date key |
| worldbank | yearly | ~196 (per country) | date + country_code |
| blockchain_com | daily | 5 (per metric) | date + metric |
| fear_greed | daily | 1 | date key |
| yfinance | business-day | 6 (per ticker) | date + ticker |
| coingecko | sub-daily | ~6 (per coin, variable) | date + coin |
| gdelt | event-based | 1,199+ (batch) | event_id only |
| cisa_kev | event-based | variable | cve_id |
| mitre_attack | event-based | variable | attack_id |
| usgs | event-based | variable | event_id |
| synthetic | hourly | variable | event_id |
| psmc | event-based | variable | event_id |

**Joinability warning:** Direct timestamp joins across sources will produce incorrect fan-outs. Treasury (1/day) joined to blockchain_com (5/day) on date produces 5x row inflation. Worldbank (196/year) joined to anything daily produces 196x inflation. Always filter by entity key (ticker, metric, country) before joining.

---

## Phase 3 — Structural Hardening

### 3.1 Source Contract Registry

```yaml
# source_contract_registry.yaml
# Defines expectations for each data source in the vault

sources:
  treasury:
    source_id: treasury
    cadence: business-day
    primary_keys: ["event_id"]  # format: tsy-{MM/DD/YY}
    natural_keys: ["payload.date"]
    timestamp_semantics: market-close (16:00 UTC)
    units:
      yields: percent (e.g., 4.86 = 4.86%)
      spread_2_10: percent (10Y - 2Y)
    caveats:
      - No weekends/holidays (275 gaps >3 days are expected)
      - Coverage: 1990-01-02 to 2024-12-31
      - No 2025+ data (dataset file not refreshed)

  worldbank:
    source_id: worldbank
    cadence: yearly
    primary_keys: ["event_id"]  # format: wb-gdp-{CC3}-{YYYY}
    natural_keys: ["payload.country_code", "payload.year"]
    timestamp_semantics: mid-year (June 30)
    units:
      value_usd: USD (current dollars, not inflation-adjusted)
      value_trillion: USD trillions (derived)
    caveats:
      - ~196 countries per year
      - Coverage: 2000-2024
      - NULL values for some country-year combinations (excluded)

  blockchain_com:
    source_id: blockchain_com
    cadence: daily
    primary_keys: ["event_id"]  # format: bc-{metric}-{unix_ts}
    natural_keys: ["payload.metric", "timestamp"]
    timestamp_semantics: midnight UTC
    units:
      hash_rate: TH/s (WARNING: values are 600M+ TH/s = 600+ EH/s)
      n_transactions: count
      n_unique_addresses: count
      mempool_size: bytes
      market_price: USD
    normalization_rules:
      - hash_rate: divide by 1e6 to get EH/s for human display
    caveats:
      - Coverage: 2025-03-02 to present (1 year)
      - 5 metrics per day = 5 events per calendar date

  fear_greed:
    source_id: fear_greed
    cadence: daily
    primary_keys: ["event_id"]  # format: fng-{unix_ts}
    natural_keys: ["timestamp"]
    timestamp_semantics: midnight UTC
    units:
      value: index 0-100 (0=extreme fear, 100=extreme greed)
      classification: text label
    caveats:
      - Coverage: 2018-02-01 to present
      - 1 gap: 2018-04-13 to 2018-04-17 (4 days)
      - Crypto-specific sentiment (not broad market)

  yfinance:
    source_id: yfinance
    cadence: business-day
    primary_keys: ["event_id"]  # format: yf-{TICKER}-{YYYYMMDD}
    natural_keys: ["payload.ticker", "timestamp"]
    timestamp_semantics: market-close (16:00 UTC)
    units:
      open/high/low/close: USD
      volume: shares (equities) or units (crypto/commodities)
    caveats:
      - Coverage: 2025-03-02 to present (1 year)
      - 6 tickers: SPY, QQQ, BTC-USD, ETH-USD, GC=F, ^VIX
      - No weekends/holidays for equity tickers
      - Crypto tickers trade 24/7 but yfinance reports daily

  coingecko:
    source_id: coingecko
    cadence: sub-daily (4hr candles for 30d window)
    primary_keys: ["event_id"]  # format: cg-{coin}-{ts_ms}
    natural_keys: ["payload.coin", "timestamp"]
    timestamp_semantics: candle open time (UTC)
    units:
      open/high/low/close: USD
    caveats:
      - Coverage: 2026-02-01 to present (30 days)
      - 3 coins: bitcoin, ethereum, solana
      - Rate limited: 30 req/min, 2.1s sleep between requests
      - Candle granularity varies by timespan (30min/4hr/4day)

  gdelt:
    source_id: gdelt
    cadence: event-based (batch ingest)
    primary_keys: ["event_id"]  # format: gdelt-{GlobalEventID}
    natural_keys: ["payload.actor1", "payload.actor2", "timestamp"]
    timestamp_semantics: event date (midnight UTC)
    units:
      goldstein_scale: -10 to +10 (conflict/cooperation)
      num_mentions: count
    caveats:
      - Coverage: 2025-03-02 to 2026-03-02
      - Batch loaded (all events for a day share same timestamp)
      - Up to 1,199 events on a single day

  cisa_kev:
    source_id: cisa_kev
    cadence: event-based
    primary_keys: ["event_id"]  # = CVE ID
    natural_keys: ["payload.cve_id"]
    timestamp_semantics: date added to KEV catalog
    units: N/A (categorical/text data)
    caveats:
      - Coverage: 2021-11-03 to 2026-02-25
      - 287 CVEs on launch day (2021-11-03)
      - due_date = remediation deadline

  mitre_attack:
    source_id: mitre_attack
    cadence: event-based
    primary_keys: ["event_id"]  # STIX object ID
    natural_keys: ["payload.attack_id"]
    timestamp_semantics: object creation date
    units: N/A (categorical/text data)
    caveats:
      - Coverage: 2017-05-31 to 2025-10-22
      - Includes techniques, groups, malware, tools, campaigns

  usgs:
    source_id: usgs
    cadence: event-based
    primary_keys: ["event_id"]  # USGS event ID
    natural_keys: ["event_id"]
    timestamp_semantics: earthquake origin time (UTC)
    units:
      magnitude: Richter scale
      depth_km: kilometers
      latitude/longitude: decimal degrees
    caveats:
      - Coverage: 2026-03-01 to 2026-03-02 (24hr snapshot)
      - Only 262 events (single API fetch)

  psmc:
    source_id: psmc
    cadence: event-based
    primary_keys: ["event_id"]  # UUID
    natural_keys: ["event_id"]
    timestamp_semantics: event creation time (UTC)
    units: varies by event type
    caveats:
      - Agent memory events (decisions, notes, milestones, beliefs)
      - Hash-chained (integrity verified)
      - Only 39 events

  synthetic:
    source_id: synthetic
    cadence: hourly (test data)
    primary_keys: ["event_id"]
    natural_keys: ["event_id"]
    timestamp_semantics: synthetic generation time
    units: varies
    caveats:
      - Test/seed data — NOT production
      - 1,958 events
      - Should be excluded from production queries

  backpack:
    source_id: backpack
    cadence: event-based
    primary_keys: ["event_id"]
    natural_keys: ["event_id"]
    timestamp_semantics: event creation time
    units: varies
    caveats:
      - Only 2 events
      - Only source with cryptographic signatures
      - Provara Backpack format (signed + chained)
```

### 3.2 Index Recommendations

**Existing indexes (adequate for current queries):**
- `idx_events_type` — covers type filtering
- `idx_events_timestamp` — covers time range queries
- `idx_events_actor` — covers actor filtering
- `idx_events_tags` — covers tag search (LIKE)
- `idx_events_format` — covers source filtering

**Recommended additions for trading strategy queries:**

```sql
-- Composite: source + timestamp (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_events_source_ts
    ON events(source_format, timestamp);

-- Composite: type + source + timestamp (filtered time series)
CREATE INDEX IF NOT EXISTS idx_events_type_source_ts
    ON events(type, source_format, timestamp);

-- Covering index for OHLCV queries (avoids table lookup)
CREATE INDEX IF NOT EXISTS idx_events_ohlcv
    ON events(source_format, timestamp)
    WHERE type = 'price.ohlcv';
```

### 3.3 Entity Namespace Proposal

```
Namespace Format: {domain}:{identifier}

asset:BTC           — Bitcoin (maps to coingecko:bitcoin, yfinance:BTC-USD)
asset:ETH           — Ethereum (maps to coingecko:ethereum, yfinance:ETH-USD)
asset:SOL           — Solana (maps to coingecko:solana)
asset:SPY           — S&P 500 ETF (yfinance:SPY)
asset:QQQ           — Nasdaq 100 ETF (yfinance:QQQ)
asset:GOLD          — Gold (yfinance:GC=F)
asset:VIX           — Volatility Index (yfinance:^VIX)

geo:US              — United States (worldbank, gdelt, treasury)
geo:{ISO3}          — Any country by ISO 3166-1 alpha-3

vuln:CVE-2024-XXXXX — CVE identifier (cisa_kev)
attack:T1059        — MITRE ATT&CK technique ID
attack:G0007        — MITRE ATT&CK group ID

chain:BTC           — Bitcoin blockchain (blockchain_com metrics)

sentiment:FNG       — Fear & Greed Index
sentiment:GDELT     — GDELT Goldstein scale

macro:CPI           — Consumer Price Index (future FRED import)
macro:UNRATE        — Unemployment Rate (future FRED import)
macro:FEDFUNDS      — Federal Funds Rate (future FRED import)
macro:GDP           — GDP (worldbank)
macro:TREASURY      — Treasury yield curve

seismic:{USGS_ID}   — Earthquake event
```

---

## Phase 4 — Findings, Risks, and Next Steps

### Findings

| # | Severity | Finding |
|---|----------|---------|
| F1 | **HIGH** | 93% of events lack hash chain (`hash`/`prev_hash` null). Tamper-evidence covers only PSMC + synthetic (~7% of vault). |
| F2 | **HIGH** | 99.99% of events lack cryptographic signatures (`sig` null). Only 2 backpack events are signed. |
| F3 | **MEDIUM** | 3 stale vault copies exist (20,886 rows each) at `~/provara/master-vault/`, `~/provara/sites/provara.dev/observatory/`, `~/provara/sites/provara-dev/observatory/`. Active vault is at 29,093 rows at `~/master-vault/`. |
| F4 | **MEDIUM** | `actor` column null on 93.3% of events. Provenance attribution missing for all bulk-imported data. |
| F5 | **MEDIUM** | Blockchain.com `hash-rate` unit label "TH/s" is misleading at 692M+ magnitude (really EH/s scale). |
| F6 | **MEDIUM** | Agent memory NDJSON (43 events) vs SQLite (41 events) discrepancy — 2 legacy events (GENESIS, OBSERVATION) lack chain fields. |
| F7 | **LOW** | All 7 Kestrel database files are empty (0 rows, schema only). |
| F8 | **LOW** | Treasury data ends at 2024-12-31. No 2025-2026 data. |
| F9 | **LOW** | USGS data is a single 24hr snapshot (262 events). Not useful for time-series analysis. |
| F10 | **INFO** | `synthetic` source (1,958 events) is test data mixed into production vault. |

### Structural Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **No integrity chain on imported data** | Cannot detect tampering of 93% of vault | Add post-import hash chain or Merkle root over imported batches |
| **Stale copies diverge silently** | Queries against wrong vault return outdated results | Delete stale copies or add symlinks to canonical location |
| **Mixed cadences in join queries** | Fan-out inflation (1 treasury row x 5 blockchain rows = 5x) | Always filter by entity key before cross-source joins |
| **No entity normalization** | "bitcoin" (coingecko) vs "BTC-USD" (yfinance) vs "chain:BTC" (blockchain_com) are the same asset | Implement entity namespace mapping table |
| **Test data in production vault** | `synthetic` source pollutes aggregates | Add `WHERE source_format != 'synthetic'` to all production queries, or remove |

### Recommended Next Steps

1. **Delete stale vault copies** — Remove `~/provara/master-vault/vault.sqlite` and both observatory copies. Symlink if needed.
2. **Add composite indexes** — `(source_format, timestamp)` and `(type, source_format, timestamp)` for trading queries.
3. **Implement entity mapping table** — Map ticker symbols to canonical entity namespaces for cross-source joins.
4. **Hash chain imported batches** — After each import run, compute Merkle root over new events and append as an integrity checkpoint event.
5. **Exclude synthetic data** — Either remove the 1,958 synthetic events or add a query filter convention.
6. **Refresh stale sources** — Treasury (missing 2025-2026), USGS (single snapshot), GDELT (single day).
7. **Normalize hash-rate units** — Store EH/s or add `unit_normalized` field to payload.
8. **Populate `actor` field** — Set `actor='import_market_data'` or similar for bulk-imported events to track provenance.
