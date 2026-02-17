# Getting Started

## Installation

```bash
pip install provara-protocol
```

## Create Your First Vault

```python
from provara.bootstrap_v0 import bootstrap
from pathlib import Path

# Create vault with dual-key authority
vault_path = Path("My_Backpack")
keys = bootstrap(vault_path, quorum=True, self_test=True)

print(f"✓ Vault created at {vault_path}")
print(f"✓ Root Key: {keys['root_key_id']}")
print(f"✓ Quorum Key: {keys['quorum_key_id']}")
```

## Add Your First Event

```python
from provara import Vault
import json

vault = Vault(vault_path)

# Record an observation
event = {
    "type": "OBSERVATION",
    "subject": "family",
    "predicate": "member",
    "value": "Alice",
    "confidence": 0.95,
}

vault.append_event(event, keys["root_key_id"], keys["root_private_key_b64"])
```

## Verify Vault Integrity

```python
from provara.backpack_integrity import compute_merkle_root
from pathlib import Path
import json

# Re-generate and compare Merkle root
files = [
    vault_path / "identity/genesis.json",
    vault_path / "events/events.ndjson",
]

computed_root = compute_merkle_root(files)
stored_root = (vault_path / "merkle_root.txt").read_text().strip()

if computed_root == stored_root:
    print("✓ Vault integrity verified")
else:
    print("✗ Tampering detected!")
```

## Sync Two Vaults

```python
from provara.sync_v0 import sync
from pathlib import Path

vault1 = Path("Vault_Desktop")
vault2 = Path("Vault_Phone")
merged = Path("Vault_Merged")

result = sync(vault1, vault2, merged)

print(f"Merged {result['new_events_in_merge']} new events")
print(f"State hash: {result['state_hash']}")
```

## Next Steps

- Read the [protocol specification](https://provara.dev/spec/)
- Check out the [module reference](./modules/)
- Join the [community](https://github.com/provara-protocol/provara)
