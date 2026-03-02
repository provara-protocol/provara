# PSMC Dual-Format Design (NDJSON + SQLite)

**Date:** 2026-03-02
**Author:** Claude Code (The Architect)
**Status:** Approved

## Problem

PSMC currently uses NDJSON-only storage. The master-vault already supports both NDJSON and SQLite. PSMC needs the same dual-format capability for fast indexed queries while preserving the append-only ndjson as source of truth.

## Design

### Write Path

Every `append_event()` writes to three targets atomically:

```
append_event()
    ├── events/events.ndjson   (existing, source of truth)
    ├── chain/chain.ndjson     (existing, signature chain)
    └── vault.sqlite           (NEW, unified schema)
```

### Schema

Uses `migrate_ndjson.MIGRATE_SCHEMA_SQL` — the unified schema supporting both Backpack and PSMC event formats with `source_format` provenance tracking and indexes on type, timestamp, actor, and tags.

### Changes to psmc.py

| Function | Change |
|----------|--------|
| `init_vault()` | Also creates `vault.sqlite` with unified schema + WAL mode |
| `append_event()` | After ndjson write, INSERT into sqlite |
| `show_events()` | Use sqlite for `--last N` and `--type` queries |
| `count_events()` | `SELECT COUNT(*)` instead of line counting |
| `verify_chain()` | No change — verifies from ndjson (source of truth) |
| `query_timeline()` | Rewrite to use sqlite for date/type/tag filtering |
| `sync_vaults()` | After ndjson merge, rebuild sqlite index |

### New CLI Commands

| Command | Purpose |
|---------|---------|
| `psmc index` | One-time: generate `vault.sqlite` from existing ndjson |
| `psmc query --type X --since Y --tags Z` | Rich querying via sqlite indexes |

### Backward Compatibility

- Vaults without `vault.sqlite` still work (ndjson fallback)
- `show` and `query` fall back to ndjson scanning if sqlite missing
- `psmc index` backfills sqlite for pre-upgrade vaults
- No changes to chain/signature format

### What Doesn't Change

- Key management, signing, verification (ndjson-based)
- Provara reducer integration
- Digest/export (reads from ndjson)
- File layout (only adds `vault.sqlite`)
