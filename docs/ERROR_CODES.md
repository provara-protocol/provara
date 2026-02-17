# Provara Error Codes (v1.0)

Normative error taxonomy for Profile A validators, sync engines, and implementations.
Implementations SHOULD emit these codes for cross-language interoperability.

Machine-readable version: [`errors.json`](../errors.json)

---

## E001–E013: Core Integrity

| Code | Name | Description |
|------|------|-------------|
| `PROVARA_E001` | `HASH_MISMATCH` | A stored hash does not equal the hash computed from the referenced data (event content, manifest file, state). |
| `PROVARA_E002` | `BROKEN_CAUSAL_CHAIN` | `prev_event_hash` does not equal the `event_id` of the actor's immediately preceding event. |
| `PROVARA_E003` | `INVALID_SIGNATURE` | Ed25519 signature verification failed. |
| `PROVARA_E004` | `EVENT_ID_MISMATCH` | Stored `event_id` does not match the deterministically computed hash of the event content. |
| `PROVARA_E005` | `CROSS_ACTOR_CHAIN_REFERENCE` | `prev_event_hash` references an event authored by a different actor. Per-actor chains MUST NOT cross. |
| `PROVARA_E006` | `ORPHAN_CHAIN_REFERENCE` | `prev_event_hash` is non-null but no event with that `event_id` exists in the log. |
| `PROVARA_E007` | `DUPLICATE_EVENT_ID` | The same `event_id` appears more than once in the event log. |
| `PROVARA_E008` | `MERKLE_ROOT_MISMATCH` | Merkle root computed from current files does not match stored `merkle_root.txt`. |
| `PROVARA_E009` | `STATE_HASH_DIVERGENCE` | Two compliant reducers produce different `state_hash` for the same event sequence. |
| `PROVARA_E010` | `MANIFEST_FILE_MISSING` | A file listed in `manifest.json` does not exist on disk. |
| `PROVARA_E011` | `MANIFEST_SIZE_MISMATCH` | A file's on-disk size does not match the size in `manifest.json`. |
| `PROVARA_E012` | `MANIFEST_HASH_MISMATCH` | A file's SHA-256 does not match the hash in `manifest.json`. |
| `PROVARA_E013` | `FIRST_EVENT_PREV_NOT_NULL` | An actor's first event has a non-null `prev_event_hash`. |

## E100–E105: Format Violations

| Code | Name | Description |
|------|------|-------------|
| `PROVARA_E100` | `HASH_FORMAT` | Hash value is not 64 lowercase hex characters. |
| `PROVARA_E101` | `EVENT_ID_FORMAT` | `event_id` does not match `evt_` + 24 lowercase hex. |
| `PROVARA_E102` | `KEY_ID_FORMAT` | `key_id` does not match `bp1_` + 16 lowercase hex. |
| `PROVARA_E103` | `SIGNATURE_FORMAT` | Signature is not valid Base64 of 64 bytes. |
| `PROVARA_E104` | `CANONICAL_FORMAT` | Canonical JSON violates RFC 8785 (key order, whitespace, number format, encoding). |
| `PROVARA_E105` | `TIMESTAMP_FORMAT` | Timestamp is not ISO 8601 UTC format ending in `Z`. |

## E200–E204: Key Management

| Code | Name | Description |
|------|------|-------------|
| `PROVARA_E200` | `KEY_ROTATION_SELF_SIGN` | A new key authorized its own `KEY_PROMOTION`. Self-signing is prohibited. |
| `PROVARA_E201` | `KEY_ROTATION_WRONG_SEQUENCE` | `KEY_PROMOTION` without a preceding `KEY_REVOCATION` for the same key. |
| `PROVARA_E202` | `KEY_ROTATION_INVALID_SIGNER` | Signer of `KEY_REVOCATION` or `KEY_PROMOTION` is not a surviving trusted authority. |
| `PROVARA_E203` | `KEY_ROTATION_BOUNDARY_MISSING` | `KEY_REVOCATION` missing required `trust_boundary_event_id` field. |
| `PROVARA_E204` | `KEY_NOT_FOUND` | `key_id` in event signature cannot be matched to any known public key. |

## E300–E303: Schema / Vault Structure

| Code | Name | Description |
|------|------|-------------|
| `PROVARA_E300` | `REQUIRED_FIELD_MISSING` | Required event field absent. Required: `event_id`, `type`, `timestamp`, `actor`, `key_id`, `sig`. |
| `PROVARA_E301` | `INVALID_CUSTOM_EVENT_TYPE` | Custom event type does not use reverse-domain prefix (e.g., `com.example.type`). |
| `PROVARA_E302` | `VAULT_STRUCTURE_INVALID` | Vault missing required paths: `events/`, `keys/`, `identity.json`, `manifest.json`. |
| `PROVARA_E303` | `SPEC_VERSION_MISMATCH` | `backpack_spec_version` is not `"1.0"`. |

## E400: Safety Tier

| Code | Name | Description |
|------|------|-------------|
| `PROVARA_E400` | `SAFETY_TIER_LOOSENING` | Merge would reduce safety tier without L3 authority. Merge ratchet (`most_restrictive_wins`) MUST be enforced. |

---

## Emission Guidance

- Emit exactly one primary code per failed check.
- Include contextual metadata (`event_id`, `actor`, `path`) in message fields.
- Preserve deterministic ordering when returning multiple errors.

Format:
```
PROVARA_E002: BROKEN_CAUSAL_CHAIN — event evt_a3f... prev_event_hash evt_b7c...
but actor alice's last event was evt_d1e...
```

## Versioning

- Version: `1.0`
- Codes are stable once published. New codes are additive only. Existing meanings MUST NOT change.
