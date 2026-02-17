# rekey_backpack

**Module:** `src/provara/rekey_backpack.py`

Key rotation protocol. Implements two-event model: KEY_REVOCATION + KEY_PROMOTION.

## Security Model

The compromised key **cannot authorize its own replacement**. Rotation must be signed by a surviving trusted authority (root or quorum key).

## Core Functions

### `rekey(vault_path: Path, old_key_id: str, new_private_key_b64: str, current_private_key_b64: str) -> None`

Perform atomic key rotation.

```python
from provara.rekey_backpack import rekey
from pathlib import Path

vault = Path("My_Backpack")

# Revoke compromised key (signed by trusted root key)
rekey(
    vault,
    old_key_id="bp1_old123...",
    new_private_key_b64="...",  # new key bytes
    current_private_key_b64="...",  # root key (authority)
)

# Creates two events:
# 1. KEY_REVOCATION (old key marked untrusted)
# 2. KEY_PROMOTION (new key marked trusted)
```

## Two-Event Model

### EVENT 1: KEY_REVOCATION

```json
{
    "type": "KEY_REVOCATION",
    "revoked_key_id": "bp1_old123...",
    "reason": "Suspected compromise",
    "timestamp_utc": "2024-02-17T16:00:00Z",
    "signed_by": "bp1_root..."
}
```

### EVENT 2: KEY_PROMOTION

```json
{
    "type": "KEY_PROMOTION",
    "new_key_id": "bp1_new456...",
    "new_public_key": "base64-encoded-32-bytes",
    "timestamp_utc": "2024-02-17T16:00:01Z",
    "signed_by": "bp1_root..."
}
```

## Chain Verification After Rekey

The sync layer verifies:

1. EVENT 1 is signed by surviving authority (not the compromised key)
2. Compromised key is marked revoked in identity/keys.json
3. EVENT 2 introduces new key and marks it active
4. No events after revocation can be signed by revoked key

## Example: Disaster Recovery

```python
from provara.rekey_backpack import rekey
from provara.backpack_signing import generate_keypair
import base64
from pathlib import Path

vault = Path("My_Backpack")

# 1. Assume root key is compromised
# 2. Use quorum key (recovery key) to revoke it

# Generate new root key
new_private, new_public = generate_keypair()
new_private_b64 = base64.b64encode(new_private).decode()

# Quorum key signs the rotation
quorum_private_b64 = "..."  # from secure storage (was in different physical location)

# Perform rotation
rekey(
    vault,
    old_key_id="bp1_root_old...",
    new_private_key_b64=new_private_b64,
    current_private_key_b64=quorum_private_b64,
)

# Result:
# - Old root key revoked
# - New root key active
# - All future events signed by quorum key until rotation completes
# - Vault chain remains unbroken
```

## Important Notes

1. **Atomicity** — Both events are added in one transaction
2. **Revocation permanent** — Revoked key can never be reactivated
3. **Chain continuity** — No events are deleted or rewritten
4. **Auditability** — Full rotation history is preserved in event log

## References

- [Provara: Key Rotation Specification](https://provara.dev/spec/)
- [Key Management Guide](https://provara.dev/keys/)
