# backpack_integrity

**Module:** `src/provara/backpack_integrity.py`

SHA-256 hashing, Merkle tree computation, path validation, and file integrity verification.

## Core Functions

### `hash_file(path: Path) -> str`

Compute SHA-256 hex digest of a file.

```python
from provara.backpack_integrity import hash_file
from pathlib import Path

file_hash = hash_file(Path("vault/events/events.ndjson"))
# Returns: "abc123..." (64-char hex)
```

### `compute_merkle_root(files: List[Path]) -> str`

Compute Merkle root over a sorted list of files. Deterministic — same files always produce same root.

```python
from provara.backpack_integrity import compute_merkle_root
from pathlib import Path

files = [
    Path("vault/identity/genesis.json"),
    Path("vault/identity/keys.json"),
    Path("vault/events/events.ndjson"),
]

root = compute_merkle_root(files)
# Returns: "def456..." (64-char hex)
```

### `validate_path_safety(path: Path, base: Path) -> bool`

Prevent directory traversal attacks. Ensure path is within base directory.

```python
from provara.backpack_integrity import validate_path_safety
from pathlib import Path

base = Path("My_Backpack")
safe_path = Path("My_Backpack/events/events.ndjson")
unsafe_path = Path("My_Backpack/../../etc/passwd")

assert validate_path_safety(safe_path, base)  # True
assert not validate_path_safety(unsafe_path, base)  # False
```

## Security Properties

- **Determinism:** Same files → same Merkle root across languages
- **Tamper-detection:** Single bit flip → different root
- **No phantom files:** Merkle tree includes only files in inventory

## Example: Vault Integrity Check

```python
from provara.backpack_integrity import compute_merkle_root
from pathlib import Path

vault_path = Path("My_Backpack")

# Collect all tracked files
tracked_files = [
    vault_path / "identity/genesis.json",
    vault_path / "identity/keys.json",
    vault_path / "events/events.ndjson",
    vault_path / "policies/safety_policy.json",
]

# Compute root
computed_root = compute_merkle_root(tracked_files)

# Compare with stored root
stored_root = (vault_path / "merkle_root.txt").read_text().strip()

if computed_root != stored_root:
    print("TAMPER DETECTED!")
else:
    print("Vault integrity verified.")
```

## References

- [FIPS 180-4: SHA-256](https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.180-4.pdf)
- [Provara: Merkle Tree Specification](https://provara.dev/spec/)
