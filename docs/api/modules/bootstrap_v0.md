# bootstrap_v0

**Module:** `src/provara/bootstrap_v0.py`

Creates a fully compliant, cryptographically-signed vault from nothing.

## What It Does

1. Generates Ed25519 keypairs (root + optional quorum)
2. Creates genesis event (vault birth certificate)
3. Builds seed policies (safety, retention, sync governance)
4. Generates manifest + Merkle root
5. Verifies output passes all 17 compliance tests

## Core Functions

### `bootstrap(vault_path: Path, quorum: bool = False, self_test: bool = False) -> Dict[str, str]`

Create a new vault at the specified path.

```python
from provara.bootstrap_v0 import bootstrap
from pathlib import Path

vault_path = Path("My_Backpack")

keys = bootstrap(vault_path, quorum=True, self_test=True)

# keys = {
#     "root_key_id": "bp1_...",
#     "root_private_key_b64": "...",
#     "quorum_key_id": "bp1_...",
#     "quorum_private_key_b64": "...",
# }
```

### Parameters

- **vault_path:** Directory to create vault in
- **quorum:** If True, generate separate recovery key (recommended)
- **self_test:** If True, run 17 compliance tests immediately

## Output Structure

```
My_Backpack/
├── identity/
│   ├── genesis.json              # Birth certificate
│   └── keys.json                 # Public key registry
├── events/
│   └── events.ndjson             # Event log (starts with GENESIS)
├── policies/
│   ├── safety_policy.json        # L0-L3 action tiers
│   ├── retention_policy.json     # Data permanence rules
│   └── sync_contract.json        # Governance structure
├── state/                        # Regeneratable from events
├── manifest.json                 # File inventory
├── manifest.sig                  # Manifest signature
└── merkle_root.txt              # Integrity anchor
```

## Genesis Event

```json
{
    "event_id": "evt_000_genesis",
    "actor": "bp1_root...",
    "type": "GENESIS",
    "timestamp_utc": "2024-02-17T16:00:00Z",
    "prev_event_hash": null,
    "payload": {
        "creator": "Provara Bootstrap v1.0",
        "vault_version": "1.0",
        "root_key_id": "bp1_root...",
        "quorum_key_id": "bp1_quorum..." // if --quorum
    },
    "signature": "..."
}
```

## Example: Create Family Vault

```python
from provara.bootstrap_v0 import bootstrap
from pathlib import Path
import json

vault_path = Path("Family_Records")

# 1. Bootstrap vault with dual-key authority
keys = bootstrap(vault_path, quorum=True, self_test=True)

print("✓ Vault created")
print(f"✓ Root Key: {keys['root_key_id']}")
print(f"✓ Quorum Key: {keys['quorum_key_id']}")

# 2. Save private keys securely (separate locations)
# In production: use HSM, KMS, or encrypted env vars
keys_file = Path("private_keys.json")
keys_file.write_text(json.dumps(keys, indent=2))
keys_file.chmod(0o600)  # Read-only by owner

print(f"✓ Private keys saved to {keys_file}")

# 3. Verify vault integrity
from provara.backpack_integrity import compute_merkle_root

files = [
    vault_path / "identity/genesis.json",
    vault_path / "events/events.ndjson",
]

root = compute_merkle_root(files)
stored_root = (vault_path / "merkle_root.txt").read_text().strip()

assert root == stored_root, "Merkle root mismatch!"
print("✓ Vault integrity verified")
```

## Key Management

After bootstrap:

1. **Root key:** Primary signing authority. Store in HSM or encrypted file.
2. **Quorum key:** Recovery key. Store in physically separate location.
3. **Backup:** Copy entire vault to USB/cloud regularly.

**NEVER commit private keys to Git.**

## Compliance Tests

Bootstrap runs 17 compliance tests:

- Directory structure (2 tests)
- Identity schema (2 tests)
- Event schema + causal chain (3 tests)
- Manifest + Merkle tree (5 tests)
- Safety policy (2 tests)
- Sync contract (1 test)

All must pass for the vault to be usable.

## References

- [Provara: Bootstrap Specification](https://provara.dev/spec/)
- [Key Management Guide](https://provara.dev/keys/)
