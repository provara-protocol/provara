# Provara Intelligence Terminal — Design Document

**Date:** 2026-03-02
**Author:** The Architect (Claude Code)
**Status:** Approved

## Purpose

A personal financial intelligence command center that surfaces actionable
market signals from the Provara vault's 20,886 events across 9 data sources
spanning 1990-2026. Single HTML file, zero server, opens locally alongside
the vault.sqlite it reads.

## Architecture

**Single file:** `master-vault/observatory.html`
Ships alongside `vault.sqlite`. User double-clicks to open.

### Dependencies (CDN-loaded, cached locally)

| Library | Version | Size | Purpose |
|---------|---------|------|---------|
| sql.js | 1.10+ | ~1.2 MB | SQLite WASM engine |
| Chart.js | 4.x | ~200 KB | All visualizations |
| chartjs-adapter-date-fns | latest | ~10 KB | Time-axis support |
| date-fns | latest | ~30 KB | Date formatting |

### Design System

Kestrel visual language (from provara.dev):
- Background: `#060a10` (deep navy)
- Cards: `#0a0e18` with `1px solid rgba(0,229,160,0.1)` border
- Accent green: `#00e5a0` (positive signals, actions)
- Accent cyan: `#00b8ff` (neutral data, links)
- Accent purple: `#8866ff` (variety, categories)
- Red: `#ff4466` (warnings, inversions, risk)
- Orange: `#ff8800` (elevated, caution)
- Text: `#c8d4e0` (base), `#e0e8f0` (bright), `#8899aa` (muted)
- Font: Space Grotesk (headings), JetBrains Mono (data/code)

## Layout — Five Zones

### Zone 1: Status Bar (top, fixed)
- Vault name, total events, time span, source count
- Last updated timestamp
- Combined risk score badge (color-coded)

### Zone 2: Macro Regime + Risk Signals (2-column)

**Left: Macro Regime Indicator**
- Current 2/10 yield spread (large number, sparkline)
- Regime classification: EXPANSION / CAUTION / RECESSION
- Historical inversion periods highlighted on sparkline
- Time-since-last-inversion or time-in-inversion counter

**Right: Risk Signal Dashboard**
- Four status lights with labels:
  - Yield Curve: NORMAL (green) / INVERTING (yellow) / INVERTED (red)
  - Cyber Threat: BASELINE (green) / ELEVATED (yellow) / CRITICAL (red)
  - Geopolitical: STABLE (green) / ELEVATED (yellow) / HIGH (red)
  - Seismic: BASELINE (green) / ACTIVE (yellow) / MAJOR (red)
- Combined risk score (0-10 scale)
- Derived from SQL queries against the vault

### Zone 3: Yield Curve Monitor (full-width)

**Current yield curve** — line chart, 1Mo through 30Yr tenors
- Solid line = latest available date
- Dashed line = 6 months prior (comparison)
- Fill area between curves (green if steepening, red if flattening)

**2/10 Spread History** — time-series chart, 1990-2024
- Line chart with zero-line emphasized
- Periods below zero (inversions) filled in red
- Annotations for recession start dates

### Zone 4: Sector Intelligence (3-column card grid)

**Card A: Cyber Threat Acceleration**
- Monthly CVE additions (bar chart, last 24 months)
- Year-over-year growth rate
- Top 3 most-targeted vendors
- Ransomware percentage
- Implication line: "Rising → bullish cyber sector"

**Card B: Geopolitical Risk Index**
- GDELT Goldstein scale monthly average (line chart)
- Cooperation vs conflict event ratio
- Top conflict dyads (actor pairs)
- Implication line: "Elevated → defense/commodities"

**Card C: Global GDP Trends**
- Top 10 economies bar chart (latest year)
- US/China/EU growth rates with trend arrows
- Emerging market aggregate
- Implication line: "Growth divergence signals"

### Zone 5: SQL Console (collapsible, bottom)
- Monospace textarea, dark theme
- Run button + Ctrl+Enter shortcut
- Results as scrollable table
- Preset query dropdown with most useful aggregations:
  - "Yield curve inversions"
  - "Monthly CVE acceleration"
  - "GDELT conflict spikes"
  - "Cross-source event density"
  - "Agent activity by type"

## Signal Derivation Logic

### Yield Curve Regime
```sql
SELECT "2 Yr", "10 Yr" FROM ... WHERE type='yield.normal' OR type='yield.inverted'
ORDER BY timestamp DESC LIMIT 1
-- If 10Yr - 2Yr < 0: INVERTED (red)
-- If 10Yr - 2Yr < 0.5: CAUTION (yellow)
-- Else: NORMAL (green)
```

### Cyber Threat Level
```sql
SELECT COUNT(*) as monthly_cves,
       substr(timestamp, 1, 7) as month
FROM events WHERE source_format='cisa_kev'
GROUP BY month ORDER BY month DESC LIMIT 3
-- Compare last 3 months vs trailing 12-month average
-- If >150% of average: CRITICAL
-- If >120% of average: ELEVATED
-- Else: BASELINE
```

### Geopolitical Risk
```sql
SELECT AVG(json_extract(payload, '$.goldstein_scale')) as avg_goldstein
FROM events WHERE source_format='gdelt'
-- If avg < -3: HIGH risk
-- If avg < 0: ELEVATED
-- Else: STABLE
```

### Seismic Activity
```sql
SELECT COUNT(*) FROM events
WHERE source_format='usgs'
  AND json_extract(payload, '$.magnitude') >= 6.0
  AND timestamp >= date('now', '-30 days')
-- If any M6.0+: MAJOR
-- If M4.5+ count > historical avg: ACTIVE
-- Else: BASELINE
```

## Interactions

- **Responsive grid** — cards reflow on narrow screens
- **Chart hover** — tooltips with exact values + dates
- **SQL console** — expand/collapse with keyboard shortcut
- **Preset queries** — dropdown populates console + auto-runs

## File Structure

```
master-vault/
├── vault.sqlite          # Data (10 MB)
├── observatory.html      # UI (single file, ~2000 lines)
└── (existing vault files)
```

## Success Criteria

1. Opens in <3 seconds from double-click
2. All 5 zones render with real data from vault.sqlite
3. Yield curve regime correctly classified
4. Risk signals derived from actual data
5. SQL console executes arbitrary queries
6. Matches Kestrel visual identity
7. Works offline, no server needed
