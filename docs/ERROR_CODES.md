# Provara Protocol v1.0 — Error Taxonomy

> Status: Normative
> Scope: Applies to all Profile A implementations
> Implementations SHOULD use these codes in error messages and logs.
> Having consistent codes prevents fragmentation when multiple language ports compare results.

---

## Code Format

```
PROVARA_E{NNN}: {SYMBOLIC_NAME}
```

- `NNN` — zero-padded 3-digit decimal, grouped by category
- Symbolic names are SCREAMING_SNAKE_CASE
- All codes are stable once published; new codes are additive only

---

## Category Map

| Range | Category |
|-------|----------|
| E001–E099 | Core chain/integrity validation |
| E100–E199 | Format violations |
| E200–E299 | Key management |
| E300–E399 | Schema / vault structure |
| E400–E499 | Safety tier |

---

## E001–E099: Core Integrity

| Code | Name | Spec Section | Description |
|------|------|-------------|-------------|
| `PROVARA_E001` | `HASH_MISMATCH` | §1, §6 | A stored or transmitted hash value does not equal the hash computed from the referenced data. Applies to event content hashes, manifest file hashes, and state_hash. |
| `PROVARA_E002` | `BROKEN_CAUSAL_CHAIN` | §7 | `prev_event_hash` does not equal the `event_id` of the actor's immediately preceding event. The causal chain is broken. |
| `PROVARA_E003` | `INVALID_SIGNATURE` | §2 | Ed25519 signature verification failed. The event payload may have been tampered with after signing, or the wrong key was used. |
| `PROVARA_E004` | `EVENT_ID_MISMATCH` | §4 | The stored `event_id` does not match the deterministically computed hash of the event content. |
| `PROVARA_E005` | `CROSS_ACTOR_CHAIN_REFERENCE` | §7 | `prev_event_hash` references an event authored by a different actor. Per-actor chains MUST NOT cross. |
| `PROVARA_E006` | `ORPHAN_CHAIN_REFERENCE` | §7 | `prev_event_hash` is non-null but no event with that `event_id` exists in the log. The chain is orphaned. |
| `PROVARA_E007` | `DUPLICATE_EVENT_ID` | §4 | The same `event_id` appears more than once in the event log. Event identity is content-addressed and MUST be unique. |
| `PROVARA_E008` | `MERKLE_ROOT_MISMATCH` | §5 | The Merkle root computed from current files does not match the stored `merkle_root.txt`. A file was added, removed, or modified after the root was committed. |
| `PROVARA_E009` | `STATE_HASH_DIVERGENCE` | §6 | Two compliant reducer implementations produce different `state_hash` values for the same event sequence. Indicates a canonicalization or reducer logic bug. |
| `PROVARA_E010` | `MANIFEST_FILE_MISSING` | §5 | A file listed in `manifest.json` does not exist on disk. |
| `PROVARA_E011` | `MANIFEST_SIZE_MISMATCH` | §5 | A file's on-disk size does not match the size recorded in `manifest.json`. |
| `PROVARA_E012` | `MANIFEST_HASH_MISMATCH` | §5 | A file's SHA-256 does not match the hash recorded in `manifest.json`. |
| `PROVARA_E013` | `FIRST_EVENT_PREV_NOT_NULL` | §7 | An actor's first event has a non-null `prev_event_hash`. The first event in any per-actor chain MUST have `prev_event_hash: null`. |

---

## E100–E199: Format Violations

| Code | Name | Spec Section | Description |
|------|------|-------------|-------------|
| `PROVARA_E100` | `HASH_FORMAT` | §1 | A hash value is not exactly 64 lowercase hexadecimal characters. |
| `PROVARA_E101` | `EVENT_ID_FORMAT` | §4 | An `event_id` does not match the pattern `evt_` + 24 lowercase hex characters. |
| `PROVARA_E102` | `KEY_ID_FORMAT` | §2 | A `key_id` does not match the pattern `bp1_` + 16 lowercase hex characters. |
| `PROVARA_E103` | `SIGNATURE_FORMAT` | §2 | A signature is not valid Base64 encoding of 64 bytes. |
| `PROVARA_E104` | `CANONICAL_FORMAT` | §3 | Canonical JSON output violates RFC 8785: keys not sorted by Unicode code point, whitespace present, numbers have leading zeros or trailing decimal zeros, or encoding is not UTF-8. |
| `PROVARA_E105` | `TIMESTAMP_FORMAT` | §4 | A timestamp is not ISO 8601 UTC format (ending in `Z`). |

---

## E200–E299: Key Management

| Code | Name | Spec Section | Description |
|------|------|-------------|-------------|
| `PROVARA_E200` | `KEY_ROTATION_SELF_SIGN` | §8 | A new key authorized its own `KEY_PROMOTION`. Self-signing is prohibited — promotion MUST be signed by a surviving trusted authority. |
| `PROVARA_E201` | `KEY_ROTATION_WRONG_SEQUENCE` | §8 | A `KEY_PROMOTION` event was encountered without a preceding `KEY_REVOCATION` event for the same key. Key rotation requires the two-event sequence: revoke then promote. |
| `PROVARA_E202` | `KEY_ROTATION_INVALID_SIGNER` | §8 | The signer of `KEY_REVOCATION` or `KEY_PROMOTION` is not a surviving trusted authority in the vault. |
| `PROVARA_E203` | `KEY_ROTATION_BOUNDARY_MISSING` | §8 | A `KEY_REVOCATION` event is missing the required `trust_boundary_event_id` field, which marks the last event trusted under the revoked key. |
| `PROVARA_E204` | `KEY_NOT_FOUND` | §2 | A `key_id` referenced in an event signature cannot be matched to any known public key in the vault. |

---

## E300–E399: Schema / Vault Structure

| Code | Name | Spec Section | Description |
|------|------|-------------|-------------|
| `PROVARA_E300` | `REQUIRED_FIELD_MISSING` | §4 | A required field is absent from an event object. Required fields: `event_id`, `type`, `timestamp`, `actor`, `key_id`, `sig`. |
| `PROVARA_E301` | `INVALID_CUSTOM_EVENT_TYPE` | §11 | A custom (non-core) event type does not use a reverse-domain prefix (e.g., `com.example.my_type`). |
| `PROVARA_E302` | `VAULT_STRUCTURE_INVALID` | §13 | The vault is missing required directories or files (e.g., `events/`, `keys/`, `identity.json`, `manifest.json`). |
| `PROVARA_E303` | `SPEC_VERSION_MISMATCH` | §12 | The vault's `backpack_spec_version` does not equal `"1.0"`. |

---

## E400–E499: Safety Tier

| Code | Name | Spec Section | Description |
|------|------|-------------|-------------|
| `PROVARA_E400` | `SAFETY_TIER_LOOSENING` | §9 | A merge operation would reduce (loosen) the safety tier of a namespace without explicit authority from an L3-cleared key. The merge ratchet rule (`most_restrictive_wins`) MUST be enforced. |

---

## Usage Guidance

### In Error Messages

Implementations SHOULD prefix errors with the code:

```
PROVARA_E002: BROKEN_CAUSAL_CHAIN — event evt_a3f... has prev_event_hash
evt_b7c... but actor alice's last event was evt_d1e...
```

### In Logs

Structured log entries SHOULD include the code as a field:

```json
{
  "level": "error",
  "provara_error": "PROVARA_E001",
  "message": "HASH_MISMATCH on event evt_3a9f...",
  "expected": "3a9f...",
  "actual": "7b2c..."
}
```

### In Test Assertions

Test vectors MAY include expected error codes:

```json
{
  "description": "tampered event should fail with HASH_MISMATCH",
  "expected_error": "PROVARA_E001"
}
```

---

## Machine-Readable Version

See [`errors.json`](../errors.json) for a structured version of this table, suitable for use in validators and code generators.

---

*Provara Protocol v1.0 — Error Taxonomy | Apache 2.0 | provara.dev*
