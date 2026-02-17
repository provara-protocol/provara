# Backpack Protocol v1.0

**Profile:** `PROVARA-1.0_PROFILE_A`
**Status:** Normative reference implementation specification
**Date:** 2026-02-16
**Source of truth:** [`PROTOCOL_PROFILE.txt`](../PROTOCOL_PROFILE.txt) — immutable after distribution. This document is the human-readable companion.

---

## Table of Contents

1. [Purpose](#1-purpose)
2. [Concepts and Vocabulary](#2-concepts-and-vocabulary)
3. [Cryptographic Stack](#3-cryptographic-stack)
4. [Canonical JSON](#4-canonical-json)
5. [Event Identity](#5-event-identity)
6. [Causal Chain](#6-causal-chain)
7. [Event Types](#7-event-types)
8. [The Reducer](#8-the-reducer)
9. [Key Management](#9-key-management)
10. [Merkle Tree](#10-merkle-tree)
11. [Manifest](#11-manifest)
12. [Safety Tiers](#12-safety-tiers)
13. [Sync Protocol](#13-sync-protocol)
14. [Event Permanence](#14-event-permanence)
15. [Directory Structure](#15-directory-structure)
16. [Compliance Requirements](#16-compliance-requirements)
17. [Reimplementation Guide](#17-reimplementation-guide)

---

## 1. Purpose

The Backpack Protocol defines a tamper-evident, append-only memory substrate for AI systems, sovereign identity, and long-lived digital institutions. A *backpack* (vault) is a directory of signed events. Given the same event log, any compliant implementation on any machine must produce byte-identical state.

**Design axiom:** *Truth is not merged. Evidence is merged. Truth is recomputed.*

Events are cryptographic evidence — signed, hashed, and causally chained. Beliefs about the world are derived by replaying evidence through a deterministic reducer. No belief is ever directly merged; only the underlying evidence is combined, and conclusions are recomputed fresh each time.

---

## 2. Concepts and Vocabulary

| Term | Definition |
|------|-----------|
| **Vault / Backpack** | A directory containing a compliant event log, identity files, policies, and manifest |
| **Event** | An immutable, content-addressed JSON record appended to the event log |
| **Actor** | The identity that authored an event (identified by `actor_key_id`) |
| **Belief** | A derived conclusion about the world — never stored directly, always recomputed from events |
| **Namespace** | One of four epistemic buckets: `canonical`, `local`, `contested`, `archived` |
| **Reducer** | The pure function `f(events) → state` that deterministically produces beliefs |
| **State hash** | A SHA-256 digest of reducer output — byte-identical across all compliant implementations |
| **Merkle root** | A SHA-256 Merkle tree root over all backpack files — seals vault integrity |
| **Manifest** | A JSON file enumerating every backpack file with its SHA-256 hash and size |
| **Fencing token** | A signed, content-addressed token that prevents stale writes during sync |
| **Key ID** | `bp1_` + first 16 hex chars of `SHA-256(raw_ed25519_public_key_bytes)` |

---

## 3. Cryptographic Stack

All Profile A implementations MUST use exactly this stack. No substitutions are permitted.

| Function | Algorithm | Specification |
|----------|-----------|---------------|
| Hashing | SHA-256 | FIPS 180-4 |
| Signing | Ed25519 | RFC 8032 |
| Canonical JSON | JCS subset | RFC 8785 |

### SHA-256 Rules

- Output: 64 lowercase hexadecimal characters
- Input: UTF-8 encoded bytes
- Used for: event IDs, file integrity, Merkle nodes, state hash, key ID derivation

### Ed25519 Rules

- Key size: 256-bit (32-byte public, 64-byte private with seed)
- Signatures: 64 bytes, Base64-encoded (standard alphabet with padding)
- Signing payload for events: `SHA-256(canonical_bytes(event_without_sig_field))`
  - The `sig` field MUST be excluded before signing
  - The `event_id` field MUST be included in the signing payload

### Key ID Derivation

```
key_id = "bp1_" + SHA-256(raw_public_key_bytes)[:16 hex chars]
```

Example: `bp1_27a6549d43046062`

---

## 4. Canonical JSON

All hashing and signing MUST use RFC 8785 canonical JSON. Two compliant implementations serializing the same logical object MUST produce byte-identical output.

### Rules (all MUST apply)

1. Object keys MUST be sorted lexicographically by Unicode code point
2. No whitespace between tokens
3. No trailing commas
4. Numbers MUST NOT have leading zeros, positive signs, or trailing decimal zeros
5. Strings MUST use minimal escape sequences
6. Encoding MUST be UTF-8 without BOM
7. Null values MUST be preserved as `"null"` — MUST NOT be omitted

### Example

Input object (logical):
```json
{"z": 3, "a": 1, "m": {"y": 2, "b": null}}
```

Canonical output:
```
{"a":1,"m":{"b":null,"y":2},"z":3}
```

### Reference Implementation

```python
import json

def canonical_bytes(obj):
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
```

Cross-language note: For fractional values (floats), prefer integer encoding or string-wrapped decimals to guarantee byte-exact interoperability across languages.

---

## 5. Event Identity

Events are content-addressed. Their ID is derived from their content.

### Derivation Rule (MUST)

1. Remove `event_id` and `sig` fields from the event object
2. Compute canonical JSON bytes of the remaining object
3. `event_id = "evt_" + SHA-256(canonical_bytes)[:24 hex chars]`

This rule is deterministic: identical event content always produces the same `event_id`.

### Example

```python
def derive_event_id(event: dict) -> str:
    hashable = {k: v for k, v in event.items() if k not in ("event_id", "sig")}
    digest = hashlib.sha256(canonical_bytes(hashable)).hexdigest()
    return f"evt_{digest[:24]}"
```

---

## 6. Causal Chain

Each actor maintains a per-actor linked list of events via `prev_event_hash`.

### Rules (all MUST apply)

1. **First event** by an actor: `prev_event_hash` MUST be `null`
2. **Subsequent events**: `prev_event_hash` MUST equal the `event_id` of that actor's immediately preceding event
3. **Cross-actor**: `prev_event_hash` MUST NOT reference another actor's events

### Integrity Rule

For any event E by actor A, if `E.prev_event_hash` is not null, there MUST exist an event P where:
- `P.event_id == E.prev_event_hash`
- `P.actor == A`

Any gap or forgery breaks the chain and fails compliance.

### Fork Detection

A *fork* occurs when two events by the same actor share the same `prev_event_hash`. This indicates concurrent offline operation. Forks are preserved in the merged log and surface in the `contested/` namespace after reducer replay.

---

## 7. Event Types

Machine-readable schema: `docs/schemas/provara_event_schema_v1.json`

### Core Types (no prefix required)

All core event types are reserved. Custom extensions MUST use reverse-domain prefixes (`com.example.my_type`).

#### GENESIS

The vault birth certificate. Every backpack has exactly one GENESIS event, written by `bootstrap_v0.py`.

Required fields:
```json
{
  "event_id": "evt_...",
  "type": "GENESIS",
  "namespace": "canonical",
  "actor": "<actor_id>",
  "actor_key_id": "<bp1_...>",
  "ts_logical": 1,
  "prev_event_hash": null,
  "timestamp_utc": "<ISO 8601>",
  "payload": {
    "uid": "<vault_uuid>",
    "birth_timestamp": "<ISO 8601>",
    "root_key_id": "<bp1_...>",
    "protocol_version": "1.0",
    "profile": "PROVARA-1.0_PROFILE_A"
  },
  "sig": "<base64 ed25519>"
}
```

#### OBSERVATION

A sensor, measurement, or belief claim with associated confidence.

```json
{
  "type": "OBSERVATION",
  "namespace": "local",
  "payload": {
    "subject": "<entity>",
    "predicate": "<property>",
    "value": "<any JSON value>",
    "confidence": 0.9,
    "timestamp": "<ISO 8601>"
  }
}
```

The belief key is `subject:predicate`. The reducer places observations in `local/`, moving them to `contested/` if conflicting high-confidence evidence accumulates.

#### ASSERTION

Functionally equivalent to OBSERVATION but defaults to lower confidence (0.35). Used for inferred or deduced beliefs rather than direct sensor readings.

#### ATTESTATION

Promotes a belief to the `canonical/` namespace. Requires institutional authority.

```json
{
  "type": "ATTESTATION",
  "namespace": "canonical",
  "payload": {
    "subject": "<entity>",
    "predicate": "<property>",
    "value": "<attested value>",
    "target_event_id": "<event_id of source evidence>",
    "actor_key_id": "<bp1_...>"
  }
}
```

When a canonical belief already exists for a key, it is moved to `archived/` with `superseded_by` set to the new attestation event ID.

#### RETRACTION

Removes a belief from active namespaces. Canonical entries are archived as retracted.

```json
{
  "type": "RETRACTION",
  "payload": {
    "subject": "<entity>",
    "predicate": "<property>"
  }
}
```

Effect:
- Removes from `local/` and `contested/`
- If in `canonical/`: moves to `archived/` with `retracted: true` and `superseded_by: <retraction_event_id>`

#### KEY_REVOCATION

Part of the two-event key rotation protocol. Marks a key as revoked.

```json
{
  "type": "KEY_REVOCATION",
  "payload": {
    "revoked_key_id": "<bp1_...>",
    "trust_boundary_event_id": "<last trusted event_id>",
    "reason": "compromised",
    "revoked_by": "<signing_key_id>"
  }
}
```

MUST be signed by a surviving trusted authority. The revoked key MUST NOT sign its own revocation.

#### KEY_PROMOTION

Second half of key rotation. Introduces the replacement key.

```json
{
  "type": "KEY_PROMOTION",
  "payload": {
    "new_key_id": "<bp1_...>",
    "new_public_key_b64": "<base64>",
    "algorithm": "Ed25519",
    "roles": ["root"],
    "promoted_by": "<signing_key_id>",
    "replaces_key_id": "<revoked_key_id>"
  }
}
```

The new key MUST NOT sign its own promotion. A surviving authority signs both rotation events.

#### REDUCER_EPOCH

Records a reducer version transition for audit purposes.

```json
{
  "type": "REDUCER_EPOCH",
  "payload": {
    "epoch_id": "<epoch_identifier>",
    "reducer_hash": "sha256:<hash_of_reducer_code>",
    "effective_from_event_id": "<event_id>",
    "ontology_versions": {"perception": "v1"}
  }
}
```

---

## 8. The Reducer

The reducer is a pure function: `f(events) → state`. Given the same event sequence, any compliant implementation MUST produce a byte-identical `state_hash`.

### Four-Namespace State Model

| Namespace | Meaning | When Populated |
|-----------|---------|----------------|
| `canonical/` | Institutionally attested truth | Via ATTESTATION event |
| `local/` | Node-local observations | Via OBSERVATION (no conflict) |
| `contested/` | Conflicting high-confidence evidence | When two conflicting observations both exceed the conflict threshold |
| `archived/` | Superseded canonical beliefs | When a canonical entry is overwritten by new ATTESTATION or RETRACTION |

### Belief Keys

Beliefs are indexed by `subject:predicate`. Example: `door_01:status`.

### Conflict Detection

The default conflict confidence threshold is `0.50`. An incoming observation triggers conflict if:

1. **Conflicts with canonical**: existing canonical value differs AND incoming confidence ≥ threshold
2. **Conflicts with local**: existing local value differs AND `max(existing_confidence, incoming_confidence)` ≥ threshold

When conflict is detected, the key moves from `local/` to `contested/` with full evidence grouping.

### Agreeing Evidence

If a new observation agrees with the existing local value:
- If incoming confidence ≤ existing: keep existing, record evidence (no state change)
- If incoming confidence > existing: update local to show higher confidence source

### State Hash

```
state_hash = SHA-256(canonical_bytes(state_without_metadata.state_hash))
```

The hash covers all four namespaces plus non-hash metadata fields. It excludes `metadata.state_hash` itself (non-self-referential). An empty reducer (zero events) produces a valid, deterministic state hash.

### Reducer Invariants

1. Same event sequence → byte-identical `state_hash`
2. Empty log → valid state hash, all namespaces empty, `event_count = 0`
3. Unknown event types: counted, ignored for state, logged to `_ignored_types`
4. Malformed events (non-dict, missing fields): skipped or handled gracefully — never crash

---

## 9. Key Management

### Key Registry (`identity/keys.json`)

```json
{
  "keys": [
    {
      "key_id": "bp1_27a6549d43046062",
      "public_key_b64": "<base64>",
      "algorithm": "Ed25519",
      "roles": ["root", "attestation"],
      "status": "active",
      "created_at_utc": "2026-02-13T00:00:00Z"
    }
  ],
  "revocations": []
}
```

### Key Rotation Protocol

Key rotation is a two-event atomic operation:

1. **KEY_REVOCATION** — signed by a surviving trusted authority (MUST NOT be the key being revoked)
2. **KEY_PROMOTION** — signed by the same surviving authority (MUST NOT be the new key)

**Security invariant:** A compromised key cannot authorize its own replacement. If an attacker could self-sign a KEY_PROMOTION, they could escalate from key compromise to permanent identity takeover.

**Trust hierarchy (for signing rotation):**
1. Non-compromised root key → signs rotation
2. Root compromised, quorum keys survive → quorum signs
3. All keys compromised → catastrophic identity death (new genesis required)

### Revoked Keys

After revocation, a key's `status` changes to `"revoked"`. Revoked keys appear in the `revocations` list and MUST NOT be used to sign new events.

---

## 10. Merkle Tree

The Merkle tree seals the integrity of all backpack files.

### Construction

1. **Leaves:** For each file entry in the manifest: `leaf_hash = SHA-256(canonical_bytes({"path": "...", "sha256": "...", "size": N}))`
2. **Ordering:** Leaves MUST be sorted lexicographically by file path
3. **Padding:** If leaf count is odd, the last leaf is duplicated
4. **Nodes:** `node_hash = SHA-256(left_child_bytes || right_child_bytes)` — raw byte concatenation (32 + 32 bytes), NOT hex string concatenation
5. **Root:** A single 64-character lowercase hex string stored in `merkle_root.txt`

### Empty Tree

An empty tree (no files) produces: `SHA-256(b"").hexdigest()`

### Reference Implementation

```python
def merkle_root_hex(leaves: list[bytes]) -> str:
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    level = [hashlib.sha256(leaf).digest() for leaf in leaves]
    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            next_level.append(hashlib.sha256(left + right).digest())
        level = next_level
    return level[0].hex()
```

---

## 11. Manifest

`manifest.json` inventories every file in the backpack with its SHA-256 hash, file size, and relative path.

### Format

```json
{
  "backpack_spec_version": "1.0",
  "manifest_format": "manifest.v0",
  "generated_at_utc": "2026-02-13T00:00:00Z",
  "merkle_root": "<64 hex chars>",
  "files": [
    {
      "path": "events/events.ndjson",
      "sha256": "<64 hex chars>",
      "size": 1234
    }
  ]
}
```

### Excluded Files

`manifest.json`, `manifest.sig`, and `merkle_root.txt` are excluded from the file list (they cannot hash themselves).

### Manifest Signature

`manifest.sig` is a detached Ed25519 signature over `SHA-256(merkle_root_bytes + canonical_bytes(manifest_header))`. It binds the manifest to a specific key and timestamp.

---

## 12. Safety Tiers

The safety tier system governs what actions a vault can authorize offline.

| Tier | Risk | Offline Allowed | Gate |
|------|------|-----------------|------|
| **L0** | Data-only, reversible | Yes | Local reducer |
| **L1** | Low-kinetic | Yes (logged for review) | Reducer + policy |
| **L2** | High-kinetic | Lease window only | Multi-sensor + signed policy |
| **L3** | Critical / irreversible | No | Human MFA or remote signature |

### Merge Ratchet

Safety constraints only tighten automatically on merge (`most_restrictive_wins`). Loosening requires a signed `POLICY_UPDATE` by a key with L3 clearance. This is a one-way ratchet — you can always become more cautious, never less cautious without explicit authority.

---

## 13. Sync Protocol

The sync protocol is a union merge with causal chain verification.

### 13.1 Chain Validation Algorithm

To validate causal and cryptographic integrity, a conformant implementation MUST execute the following deterministic procedure:

1. Parse all NDJSON lines as UTF-8 JSON objects.
2. Build `event_by_id[event_id]` and fail on duplicate IDs.
3. For each event:
   - Recompute content-derived ID from the event with `event_id` and `sig` removed.
   - Verify recomputed ID equals `event_id`.
4. Build `actor_events[actor]` and sort each actor list by:
   - `timestamp_utc` (primary, ascending)
   - `event_id` (secondary, ascending)
5. For each actor chain:
   - First event MUST have `prev_event_hash = null`.
   - Each subsequent event MUST set `prev_event_hash` to the immediately preceding event ID in that actor-sorted list.
   - `prev_event_hash` MUST reference an event by the same actor (cross-actor references are invalid).
6. For each signed event:
   - Resolve public key by `actor_key_id`.
   - Reject missing, unknown, or revoked key IDs.
   - Verify Ed25519 signature over canonical JSON bytes of event-without-`sig`.
7. If all checks pass, the chain is valid; otherwise invalid with a specific error code (see §16.1).

### 13.2 Algorithm Pseudocode

```
function verify_vault(events):
    event_by_id = {}
    actor_events = {}

    for e in events:
        require_utf8_json(e)                                   # PROVARA_E007
        require_required_fields(e)                             # PROVARA_E004
        if e.event_id in event_by_id:
            fail(PROVARA_E010, "DUPLICATE_EVENT_ID")
        event_by_id[e.event_id] = e

        derived = derive_event_id(remove_fields(e, ["event_id", "sig"]))
        if derived != e.event_id:
            fail(PROVARA_E001, "HASH_MISMATCH")

        actor_events[e.actor].append(e)

    for actor in actor_events:
        chain = sort(actor_events[actor], by=["timestamp_utc", "event_id"])
        for i in range(0, len(chain)):
            curr = chain[i]
            if i == 0:
                if curr.prev_event_hash is not null:
                    fail(PROVARA_E002, "BROKEN_CAUSAL_CHAIN")
            else:
                prev = chain[i - 1]
                if curr.prev_event_hash != prev.event_id:
                    fail(PROVARA_E002, "BROKEN_CAUSAL_CHAIN")

                # explicit same-actor check for referenced prev
                linked = event_by_id.get(curr.prev_event_hash)
                if linked is null or linked.actor != actor:
                    fail(PROVARA_E011, "CROSS_ACTOR_REFERENCE")

            if has_field(curr, "sig"):
                key = key_registry.get(curr.actor_key_id)
                if key is null:
                    fail(PROVARA_E012, "UNKNOWN_KEY_ID")
                if key.status == "revoked":
                    fail(PROVARA_E006, "REVOKED_KEY_USE")
                if !verify_ed25519_signature(curr, key.public_key):
                    fail(PROVARA_E003, "INVALID_SIGNATURE")

    return ok()
```

### 13.3 Fencing Tokens

Before writing to a backpack, generate a fencing token:

```
token_hash = SHA-256(latest_event_id + ":" + timestamp + ":" + nonce)
sig = Ed25519_sign(token_hash, active_key)
```

Validation:
1. Recompute `token_hash` from the fields
2. Verify signature against key registry
3. Verify `latest_event_id` still exists in the event log

A stale token (referencing an event that was superseded by a merge) fails validation, preventing lost-update scenarios.

### Delta Export / Import

Delta bundles enable partial sync (only events after a known hash):

```
Header: {"type": "provara_delta_v1", "since_hash": "...", "event_count": N, "keys": [...]}
Body:   One NDJSON line per event
```

Unknown event types MUST be preserved in the merged log. They MUST NOT affect core reducer state.

---

## 14. Event Permanence

Events MUST be permanent. Implementations MUST NOT delete events.

| Data Type | Retention |
|-----------|-----------|
| Events | Permanent |
| Checkpoints | Permanent |
| Perception raw data | 30-day default, oldest-first eviction (MAY vary) |
| CAS artifacts | Permanent if referenced; 90-day if unreferenced (MAY vary) |
| State caches | MAY be evicted (regeneratable from events) |

---

## 15. Directory Structure

```
My_Backpack/
├── identity/
│   ├── genesis.json              # Birth certificate
│   └── keys.json                 # Public key registry
├── events/
│   └── events.ndjson             # THE source of truth (append-only NDJSON)
├── policies/
│   ├── safety_policy.json        # L0-L3 kinetic risk tiers
│   ├── retention_policy.json     # Data permanence rules
│   ├── sync_contract.json        # Governance + authority ladder
│   └── ontology/
│       └── perception_ontology_v1.json
├── state/                        # Regeneratable cache (may be absent)
│   └── current_state.json
├── artifacts/
│   └── cas/                      # Content-addressed storage
├── manifest.json                 # File inventory with SHA-256 hashes
├── manifest.sig                  # Ed25519 signature over manifest
└── merkle_root.txt               # Integrity anchor (single hex string)
```

### Path Safety

All file paths in the manifest MUST:
- Be relative to the backpack root
- Not contain `..` or symlinks pointing outside the root
- Be lexicographically sorted in the manifest

---

## 16. Compliance Requirements

### 16.1 Error Taxonomy

Standardized error codes for validation failures. Implementations SHOULD use these codes to ensure interoperability and clear auditing.

| Code | Label | Description |
|------|-------|-------------|
| `PROVARA_E001` | `HASH_MISMATCH` | Event ID does not match computed content hash |
| `PROVARA_E002` | `BROKEN_CAUSAL_CHAIN` | `prev_event_hash` does not link to correct previous event |
| `PROVARA_E003` | `INVALID_SIGNATURE` | Signature verification failed for the given public key |
| `PROVARA_E004` | `MISSING_FIELD` | A required top-level or payload field is missing |
| `PROVARA_E005` | `UNAUTHORIZED_SIGNER` | The signing key does not have authority for the event type |
| `PROVARA_E006` | `REVOKED_KEY_USE` | Event signed by a key that was revoked at the time of signing |
| `PROVARA_E007` | `MALFORMED_JSON` | Event or file is not valid UTF-8 or standard JSON |
| `PROVARA_E008` | `MERKLE_ROOT_MISMATCH` | Recomputed Merkle root does not match `merkle_root.txt` |
| `PROVARA_E009` | `UNSAFE_PATH` | Manifest entry path is absolute, traverses `..`, or escapes root |
| `PROVARA_E010` | `DUPLICATE_EVENT_ID` | Duplicate `event_id` found in a log that requires uniqueness |
| `PROVARA_E011` | `CROSS_ACTOR_REFERENCE` | Event references previous hash from a different actor chain |
| `PROVARA_E012` | `UNKNOWN_KEY_ID` | `actor_key_id` cannot be resolved in active key registry |

Canonical source for these codes: `docs/ERROR_CODES.md`

### 16.2 Minimum Test Coverage

| Category | Tests | Requirement |
|----------|------:|-------------|
| Directory structure | 2 | Required folders and files exist |
| Identity schema | 2 | Genesis event and key registry validity |
| Event schema + causal chain | 3 | Event format, uniqueness, causal ordering |
| Manifest integrity + Merkle | 5 | File hashes, Merkle computation, no phantoms, path safety |
| Safety policy structure | 2 | L0-L3 structure and ratchet constraints |
| Sync contract schema | 1 | Governance schema validity |
| Reducer determinism | 1 | Same events → identical state hash |
| Retention permanence | 1 | Events are never deleted |

Run against the reference backpack:
```bash
cd SNP_Core/test && PYTHONPATH=../bin python backpack_compliance_v1.py ../examples/reference_backpack -v
```

---

## 17. Reimplementation Guide

To implement Provara v1.0 in another language:

### Step 1 — Cryptographic Primitives

Implement:
- SHA-256 (FIPS 180-4)
- Ed25519 sign and verify (RFC 8032)
- RFC 8785 canonical JSON

### Step 2 — Validate Against Test Vectors

Validate your implementations against `test_vectors/vectors.json`. The 7 vectors cover canonical JSON, SHA-256, event ID derivation, key ID derivation, Ed25519 sign/verify, Merkle root, and reducer determinism.

### Step 3 — Implement the Reducer

Handle: `OBSERVATION`, `ASSERTION`, `ATTESTATION`, `RETRACTION`, `REDUCER_EPOCH`, `KEY_REVOCATION`, `KEY_PROMOTION`

For unknown event types: count them, do not modify namespace state, preserve in event log on merge.

### Step 4 — Verify Determinism

Run your reducer against the test vector event sequence. Compare your `state_hash` to the reference value. If they match, your implementation is correct. If they diverge, the canonical JSON or hash computation has a bug.

### Step 5 — Pass Compliance Tests

Generate a backpack with your implementation and run the 17 compliance tests. If all pass, your implementation is conformant.

### If State Hashes Diverge

Common causes:
1. **Non-canonical JSON** — check key sorting, whitespace, null handling
2. **Float serialization** — JSON float encoding differs across languages; use integers or string-wrapped values for fractional confidence scores
3. **UTF-8 encoding** — ensure no BOM, no alternate encodings
4. **Missing metadata fields** — `state_hash` excludes `metadata.state_hash` but includes all other metadata fields

The Python reference implementation is the canonical source of truth for any ambiguity.

---

## 18. Security Considerations

### 18.1 Threat Model

| Threat | Primary Defense | Residual Risk / Operator Duty |
|--------|------------------|-------------------------------|
| **Payload/data tampering** | Event signatures + manifest file hashes + Merkle root verification | Private key compromise can still produce valid malicious events until revocation. |
| **History re-ordering** | Per-actor causal chain (`prev_event_hash`) + deterministic sort on replay | Incorrect timestamp parsing in non-conformant ports can still cause divergence. |
| **Silent deletion / truncation** | Missing links (`prev_event_hash`) and manifest mismatch detection | Deletion of newest tail events can appear as a stale snapshot if no external anchor/checkpoint is compared. |
| **Identity takeover** | Rotation requires surviving signer; self-promotion is prohibited | If all authorities are compromised, identity continuity is cryptographically lost (new genesis required). |
| **Stale-write overwrite** | Fencing token includes latest event ID, timestamp, nonce, and signature | Long offline windows increase merge complexity and contested state volume. |
| **Fork-and-discard (equivocation)** | Fork detection by identical actor + identical `prev_event_hash`; conflicting branches remain auditable | Governance must define how forks are adjudicated and whether one branch is quarantined. |
| **Time/backdating manipulation** | Event ID is content-addressed and signed; chain linkage is authoritative, not wall-clock time | `timestamp_utc` is still untrusted metadata and can mislead human readers if not cross-checked. |
| **Resource-exhaustion (DoS)** | Streaming hash/verification, bounded input handling, malformed-line rejection | Operators must enforce max event size, max payload depth, and replay quotas in production deployments. |
| **Key ID collision attempt** | Key IDs are SHA-256-derived; practical collision resistance at current security levels | Profile migration plan needed if SHA-256 security assumptions materially degrade in future. |

### 18.2 Mandatory Validation Order

To reduce attack surface and ambiguous error handling, implementations SHOULD validate in this order:

1. UTF-8 + JSON parse checks
2. Required field checks
3. Event ID recomputation checks
4. Causal chain linkage checks
5. Key resolution/revocation checks
6. Signature verification checks
7. Manifest and Merkle verification checks

Fail closed at the first critical invariant break and emit the corresponding `PROVARA_E###` code.

### 18.3 Replay and Duplication Attacks

Replay of already-seen events is constrained by unique `event_id` and dedup rules. Implementations MUST reject duplicate IDs in contexts that require uniqueness and MUST NOT permit duplicate events to mutate derived state more than once.

For delta import/sync workflows, unknown event types are preserved, but replayed known events still require full ID/signature/chain validation before acceptance.

### 18.4 Truncation and Partial Snapshot Risk

Protocol checks can prove integrity of what is present; they cannot prove the local copy is globally complete without comparison to a stronger anchor (signed checkpoint, remote peer state, or externally pinned digest).

Operational guidance:

- Keep signed checkpoints.
- Compare latest known event IDs across peers.
- Treat unexplained chain-head regressions as incident conditions.

### 18.5 Time Semantics and Backdating

`timestamp_utc` supports ordering and audit readability but is not a trust root. Chain linkage and signatures are authoritative. Implementations SHOULD prefer deterministic chain order (`timestamp_utc`, then `event_id`) and SHOULD log suspicious clock drift for operators.

### 18.6 Privacy and Confidentiality

Provara provides integrity and authenticity, not confidentiality. Events are plaintext JSON unless encrypted upstream.

Recommendations:

- Encrypt sensitive payloads before event creation.
- Avoid direct storage of PII/secrets in `payload.value`.
- Separate key-management concerns from vault transport/storage concerns.

### 18.7 Key Compromise and Rotation Boundaries

Key compromise is handled by `KEY_REVOCATION` + `KEY_PROMOTION` signed by surviving authority. Implementations SHOULD surface `trust_boundary_event_id` prominently in audit output to distinguish trusted pre-compromise history from post-compromise uncertainty.

### 18.8 Denial-of-Service Considerations

Implementations SHOULD set explicit limits for:

- maximum event byte size
- maximum payload nesting depth
- maximum lines processed per import batch
- maximum replay wall-clock budget before checkpoint fallback

Malformed input MUST be rejected or quarantined deterministically, never silently coerced into valid state transitions.

### 18.9 Cryptographic Agility

Profile A fixes SHA-256 and Ed25519 for interoperability. Future profiles SHOULD define migration events and dual-signing windows for algorithm transition (including post-quantum profiles) without breaking append-only verification semantics.

---

*Derived from `PROTOCOL_PROFILE.txt` (frozen normative spec). In case of conflict, the profile wins.*
