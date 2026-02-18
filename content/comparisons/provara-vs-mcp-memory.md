# Provara vs MCP Memory: A Technical Comparison

**Date:** 2026-02-18
**Status:** Reference document

---

## Executive Summary

MCP Memory (the reference in-process memory server from the MCP SDK examples) and Provara MCP serve different goals: MCP Memory is a volatile, unverified key-value store, while Provara MCP is a persistent, cryptographically verifiable event log. This document explains the tradeoff and provides a migration path.

---

## Side-by-Side Comparison

| Property | MCP Memory (reference) | Provara MCP |
|----------|------------------------|-------------|
| **Persistence** | In-process only (lost on restart) | Durable NDJSON on disk |
| **Data model** | Key-value pairs | Typed events with typed payloads |
| **Tamper-evidence** | None | Ed25519 signatures + SHA-256 chain |
| **Audit trail** | None | Full append-only event log |
| **Independent verification** | Not possible | `verify.py` bundle, no Provara needed |
| **Corrections** | Overwrite (original lost) | Append CORRECTION event (original preserved) |
| **Chain integrity** | Not applicable | Merkle root + sequential hash chain |
| **Query** | Key lookup | Actor, type, time-range (SQLite index) |
| **Conflicts** | Not detected | `list_conflicts` surfaces contradictions |
| **Digests** | Not available | `generate_digest` → weekly Markdown |
| **Snapshots** | Not available | `checkpoint_vault` + `snapshot_belief` |
| **Forensic export** | Not available | `forensic_export` → self-contained bundle |
| **Transport** | stdio | stdio, SSE, streamable-http |
| **Dependencies** | None | `cryptography>=41.0`, `mcp>=1.0` |

---

## Architectural Difference

### MCP Memory

```
Agent → MCP Memory Server → in-memory dict
                          ↓ (restart)
                         lost
```

MCP Memory is useful for ephemeral context within a single session. There is no signing, no chain, and no way to prove what the agent knew at any point in time.

### Provara MCP

```
Agent → Provara MCP Server → events.ndjson (disk)
                                   ↓
                           Ed25519 sign each event
                                   ↓
                           SHA-256 chain to prev
                                   ↓
                           Merkle root over all
```

Provara persists every event with a cryptographic proof of when it was recorded and that it has not been altered since. The record survives server restarts and can be audited by a third party who has never seen the software before.

---

## When to Use Each

### Use MCP Memory when:
- You need a scratch pad for a single conversation
- No audit requirement exists
- You don't need to replay or verify what the agent knew
- Simplicity is the only goal

### Use Provara MCP when:
- Memory must survive restarts (agent sessions, deployments)
- You need to prove what the agent believed at a specific time
- Users or regulators can request an audit trail
- Corrections must preserve the original claim
- Multiple agents share memory and conflicts must be surfaced
- You want a forensic export for legal or compliance purposes

---

## Migration Guide: MCP Memory → Provara MCP

### Step 1: Initialize a vault

```bash
pip install provara-protocol[mcp]
provara init ~/my_agent_vault --actor my_agent
```

### Step 2: Update claude_desktop_config.json

**Before (MCP Memory):**
```json
{
  "mcpServers": {
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    }
  }
}
```

**After (Provara):**
```json
{
  "mcpServers": {
    "provara": {
      "command": "provara-mcp"
    }
  }
}
```

### Step 3: Replace tool calls

| MCP Memory | Provara MCP | Notes |
|------------|-------------|-------|
| `create_entities` | `append_event` with `event_type="ENTITY"` | Provara event_type is free-form |
| `add_observation` | `append_event` with `event_type="OBSERVATION"` | Add `subject`, `predicate`, `value` to data |
| `create_relations` | `append_event` with `event_type="RELATION"` | Include both entities in data |
| `read_graph` | `query_timeline` or `export_markdown` | Timeline gives typed events; markdown gives full history |
| `search_nodes` | `query_events` with `event_type` filter | Filter by type; combine with actor filter |
| `delete_entities` | Not supported (append-only) | Append `event_type="RETRACTION"` instead |
| `delete_observations` | Not supported (append-only) | Append `event_type="CORRECTION"` instead |
| `delete_relations` | Not supported (append-only) | Append `event_type="RETRACTION"` instead |
| `open_nodes` | `query_events` with `actor` filter | Actor-scoped view of the vault |

### Step 4: Verify the migration

```bash
# Confirm vault structure and chain integrity
provara verify ~/my_agent_vault

# Export full history to Markdown for review
provara export-markdown ~/my_agent_vault --output history.md
```

---

## Data Model Mapping

### MCP Memory entity
```json
{
  "name": "Alice",
  "entityType": "Person",
  "observations": ["Alice is a researcher", "Alice works at MIT"]
}
```

### Equivalent Provara events
```json
{"type": "ENTITY", "actor": "my_agent", "payload": {"name": "Alice", "entity_type": "Person"}, ...}
{"type": "OBSERVATION", "actor": "my_agent", "payload": {"subject": "Alice", "predicate": "is", "value": "a researcher"}, ...}
{"type": "OBSERVATION", "actor": "my_agent", "payload": {"subject": "Alice", "predicate": "works_at", "value": "MIT"}, ...}
```

Provara events are richer: each has a content-addressed `event_id`, `prev_event_hash`, Ed25519 `sig`, and `timestamp_utc`. The entity and its observations are separate events in the append-only log — corrections are additive, not destructive.

---

## Verification

Provara enables verification that MCP Memory cannot:

```bash
# Prove what the agent knew at 2026-02-18T10:00:00Z
provara query ~/my_agent_vault --before 2026-02-18T10:00:00Z

# Export forensic bundle for third-party audit
provara forensic-export ~/my_agent_vault --output audit_bundle/

# Verify bundle integrity without Provara installed
python audit_bundle/verify.py
```

The forensic bundle includes a standalone `verify.py` that requires only the `cryptography` package and exits 0 if all signatures and hash chains are valid.

---

## Summary

MCP Memory is a scratch pad. Provara is an audit log. For applications where accountability, persistence, or verifiability matter — regulated industries, multi-agent systems, long-running deployments — Provara MCP provides the cryptographic foundation that MCP Memory was never designed to offer.

Both are valid tools with different scopes. This document helps teams understand when to graduate from ephemeral memory to verifiable memory.
