# manifest_generator

**Module:** `src/provara/manifest_generator.py`

Generates `manifest.json` and `merkle_root.txt` for a backpack directory. Provides signed file inventory + integrity anchor.

## Core Functions

### `generate_manifest(vault_path: Path) -> Dict[str, Any]`

Generate manifest (file inventory + SHA-256 hashes) for a vault.

```python
from provara.manifest_generator import generate_manifest
from pathlib import Path

vault = Path("My_Backpack")
manifest = generate_manifest(vault)

# manifest["files"] → {"path": "hash", ...}
# manifest["merkle_root"] → hex string
# manifest["timestamp"] → ISO 8601
```

### `write_manifest(vault_path: Path, manifest: Dict[str, Any], manifest_sig: str)`

Write manifest.json and merkle_root.txt to vault.

```python
from provara.manifest_generator import write_manifest

write_manifest(vault, manifest, signature)
# Creates: vault/manifest.json, vault/manifest.sig, vault/merkle_root.txt
```

## Example: Sealing a Vault

```python
from provara.manifest_generator import generate_manifest, write_manifest
from provara.backpack_signing import sign_manifest
from pathlib import Path
import base64

vault = Path("My_Backpack")

# 1. Generate manifest
manifest = generate_manifest(vault)

# 2. Sign manifest
manifest_header = {
    "version": "1.0",
    "timestamp": manifest["timestamp"],
}

private_key_b64 = "..."  # from secure storage

signature = sign_manifest(
    manifest["merkle_root"],
    manifest_header,
    private_key_b64
)

# 3. Write to vault
write_manifest(vault, manifest, signature)
```

## Integrity Verification

```python
from provara.manifest_generator import generate_manifest
from pathlib import Path
import json

vault = Path("My_Backpack")

# Re-generate manifest from current vault state
current_manifest = generate_manifest(vault)

# Read stored manifest
stored_manifest = json.loads((vault / "manifest.json").read_text())

# Compare Merkle roots
if current_manifest["merkle_root"] != stored_manifest["merkle_root"]:
    print("TAMPERING DETECTED!")
else:
    print("Vault intact.")
```

## References

- [Provara: Manifest Specification](https://provara.dev/spec/)
