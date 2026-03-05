# Sovereign Schema Integration Design

**Date:** 2026-03-05
**Status:** Approved
**Author:** The Architect (Claude Code)

## Overview

Wire the AEE type system (`sovereign_schema.py`) into Provara's CLI and vault pipeline as a first-class citizen alongside existing backpack events. Single NDJSON chain, unified verification, extended reducer.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | Single `events.ndjson` | One chain = one source of truth, aligns with append-only philosophy |
| Reducer | Extend `SovereignReducerV0` | Additive, not a rewrite; promote to V1 later if needed |
| CLI surface | Generic `--schema sovereign --payload-type X` flags | Minimal surface, Pydantic validates; convenience subcommands can come later |
| Verification | Unified auto-detect | `provara verify` runs strongest checks available; `--pipeline` opt-in for completeness |

## Architecture

```
                    CLI Entry Point
                         |
            +------------+------------+
            |                         |
    --schema sovereign          (default backpack)
    --payload-type SwapIntent     --type OBSERVATION
    --data '{...}'                --data '{...}'
            |                         |
    +-------v--------+        +-------v--------+
    | Pydantic V2    |        | Dict-based     |
    | strict validate|        | validation     |
    | ProvaraEvent   |        | sign_event()   |
    | .from_payload()|        |                |
    | .seal()        |        |                |
    +-------+--------+        +-------+--------+
            |                         |
            +------------+------------+
                         |
              events.ndjson (single chain)
                         |
            +------------+------------+
            |                         |
      provara verify            provara replay
      (auto-detects             (SovereignReducerV0
       sovereign events,         extended with
       checks payload_digest,    sovereign dispatch)
       sequence, chain +
       --pipeline for
       completeness)
```

## Components

### 1. CLI Extension (cli.py)

Extend `cmd_append()` with two new flags:

- `--schema sovereign` triggers sovereign event path
- `--payload-type <TYPE>` selects: SwapIntent, LendingAction, AllocationRebalance, EmergencyHalt

Sovereign path:
1. Parse `--data` JSON through matching Pydantic model (strict validation)
2. Require `--type` to be a valid `EventType` enum value
3. Build event via `ProvaraEvent.from_payload()`
4. Sign via existing keyfile flow, seal via `.seal()`
5. Append `.to_ndjson_line()` to `events.ndjson`

Absent `--schema` flag: existing backpack path, unchanged.

### 2. Unified Verification (cmd_verify)

Auto-detect sovereign events by presence of `schema_version` field:

- **Always**: payload_digest matches recomputed SHA256(canonical_json(payload))
- **Always**: sequence_number monotonically increasing across sovereign events
- **Always**: chain links (existing + sovereign's previous_event_digest)
- **Opt-in** `--pipeline`: run verify_pipeline_completeness() on ACTION_PROPOSED events

Both event types share the same hash chain. Each event's prev_hash references the previous event regardless of type.

### 3. Reducer Extension (SovereignReducerV0)

Add sovereign event dispatch alongside existing OBSERVATION/ASSERTION handling. Detection: `schema_version` key present = sovereign dispatch, else backpack dispatch.

| EventType | State Update |
|-----------|-------------|
| ACTION_PROPOSED | Append to `state["pending_actions"]` |
| ACTION_EXECUTED | Move pending -> `state["executed_actions"]`, update `state["positions"]` |
| ACTION_REJECTED / ACTION_EXPIRED | Remove from `state["pending_actions"]` |
| CIRCUIT_BREAKER_TRIGGERED | Set `state["halted"] = True` |
| CIRCUIT_BREAKER_RESET | Set `state["halted"] = False` |
| CONSTITUTION_CREATED | Store in `state["constitution"]` |
| SIGNAL_DETECTED, SIMULATION_COMPLETE, AUDIT_PASSED | Append to `state["pipeline_log"]` |
| All other sovereign types | Append to `state["sovereign_events"]` (catch-all) |

### 4. Canonical JSON Consolidation

Both systems produce identical bytes. Replace sovereign_schema's inline `canonical_json()` with import from `provara.canonical_json.canonical_bytes()`. Keep `sha256_hex()` in sovereign_schema (trivial one-liner).

### 5. SQLite Indexing

Extend query schema:
- Add `schema_version` column (nullable, NULL for backpack events)
- Add `payload_type` column (nullable)
- Sovereign events queryable via `provara query --type ACTION_PROPOSED`

## Out of Scope

- New CLI subcommands (keeping surface small)
- Separate NDJSON files
- New reducer (extending V0 only)
- Breaking changes to backpack events
- zkVM proof generation (future)
- ConstitutionV1 / SessionKeyPolicy CLI commands (programmatic use only)

## Testing Strategy

- Unit tests: sovereign append path (valid + invalid payloads)
- Chain integrity: mixed backpack + sovereign events
- Reducer: sovereign event types produce expected state
- Round-trip: append sovereign -> verify -> replay -> check state
- Regression: all existing 646 tests still pass
