# Vault Archival Rotation Spec

## 1. Overview
Provara vaults are designed for long-term (50+ year) data preservation. However, as vaults grow, they can become unwieldy for active use. Archival rotation allows an operator to "close" a vault and start a new one while maintaining a verifiable cryptographic link to the entire history.

## 2. Vault Lifecycle

1.  **Active vault**: Normal operation. Events are appended, and the vault is mutable (append-only).
2.  **Sealed vault**: Permanently closed. No more events can be appended. The vault is now a read-only historical record.
3.  **Successor vault**: A new vault that starts fresh but contains a `predecessor_vault` pointer in its genesis event.

## 3. Seal Ceremony

To seal a vault, a final event of type `com.provara.vault.seal` is appended to the event log.

### Seal Event Schema
```json
{
  "type": "com.provara.vault.seal",
  "actor": "actor_id",
  "timestamp_utc": "ISO8601_TIMESTAMP",
  "payload": {
    "reason": "archival_rotation",
    "final_event_count": 1234567,
    "final_merkle_root": "sha256_hex",
    "seal_timestamp": "ISO8601_TIMESTAMP"
  }
}
```

### Constraints
- Once a `com.provara.vault.seal` event is present in `events.ndjson`, any further attempts to append events to that vault MUST be rejected.
- The seal event must be signed by an authorized key.

## 4. Successor Creation

A successor vault is initialized with a special `predecessor_vault` field in its `GENESIS` event.

### Genesis Successor Schema
```json
{
  "type": "GENESIS",
  "payload": {
    "uid": "new_vault_uid",
    "predecessor_vault": {
      "merkle_root": "predecessor_final_merkle_root",
      "final_event_count": 1234567,
      "seal_event_id": "evt_...",
      "seal_event_hash": "hash_of_seal_event"
    }
  }
}
```

## 5. Verification Across Rotations

Verification can be extended to follow the chain of predecessors.

1.  Verify the current vault normally.
2.  If a `predecessor_vault` is present in genesis:
    - Locate the predecessor vault.
    - Verify its integrity.
    - Confirm its final state (Merkle root, event count, seal event) matches the pointer in the successor's genesis.
    - Recursively follow predecessors until the original genesis is reached.

## 6. CLI Commands

- `provara seal <vault_path> --keyfile <path>`: Appends a seal event to the vault.
- `provara rotate-vault <sealed_vault> --successor <new_path> --keyfile <path>`: Creates a new successor vault linked to the sealed predecessor.
- `provara verify <vault> --follow-predecessors`: Verifies the vault and all its predecessors.
