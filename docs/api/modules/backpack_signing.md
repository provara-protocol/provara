# backpack_signing

**Module:** `src/provara/backpack_signing.py`

Ed25519 cryptographic signing layer. Implements RFC 8032 signing and verification.

## Security Model

- **Private keys NEVER in the backpack** — Lives in HSM, env var, or operator keyfile
- **Public keys in identity/keys.json** — Registry of trusted signers
- **Detached signatures** — Event carries `signature` field (Ed25519 over canonical JSON)
- **Key authority** — Signing key must be active (not revoked, not future)

## Core Functions

### `generate_keypair() -> Tuple[bytes, bytes]`

Generate Ed25519 private + public key (32 bytes each).

```python
from provara.backpack_signing import generate_keypair
import base64

private_key, public_key = generate_keypair()

# Store private key securely (e.g., env var, file with 0600 perms)
# Register public key in identity/keys.json
```

### `sign_event(event: Dict[str, Any], private_key_b64: str) -> str`

Sign an event with Ed25519. Returns base64-encoded signature.

```python
from provara.backpack_signing import sign_event
import base64

event = {
    "event_id": "evt_001",
    "actor": "bp1_alice...",
    "type": "OBSERVATION",
    "subject": "x",
    "predicate": "p",
    "value": 1,
}

# private_key_b64 is base64-encoded 32-byte Ed25519 private key
private_key_b64 = "..."  # from secure storage

signature_b64 = sign_event(event, private_key_b64)

# Add to event
event["signature"] = signature_b64
```

### `verify_event(event: Dict[str, Any], public_key_b64: str) -> bool`

Verify an event signature with Ed25519. Returns True if valid.

```python
from provara.backpack_signing import verify_event

is_valid = verify_event(event, public_key_b64)

if not is_valid:
    raise ValueError(f"Signature invalid for event {event['event_id']}")
```

### `sign_manifest(merkle_root: str, manifest_header: Dict[str, Any], private_key_b64: str) -> str`

Sign manifest + Merkle root. Used in vault sealing.

```python
from provara.backpack_signing import sign_manifest

manifest_header = {
    "merkle_root": "abc123...",
    "version": "1.0",
    "timestamp": "2024-02-17T16:00:00Z"
}

manifest_sig = sign_manifest("abc123...", manifest_header, private_key_b64)
```

### `verify_manifest(merkle_root: str, manifest_header: Dict[str, Any], manifest_sig: str, public_key_b64: str) -> bool`

Verify manifest signature.

```python
from provara.backpack_signing import verify_manifest

is_valid = verify_manifest(
    merkle_root,
    manifest_header,
    manifest_sig,
    public_key_b64
)
```

## Key ID Format

Key IDs follow the Backpack v1 format:

```
bp1_<16-char-hex>

Where <16-char-hex> = SHA-256(public_key_bytes)[:16]
```

Example: `bp1_a1b2c3d4e5f6g7h8`

## Example: Full Signing Workflow

```python
from provara.backpack_signing import (
    generate_keypair,
    sign_event,
    verify_event,
)
import base64
from provara.canonical_json import canonical_hash

# 1. Generate keys
private_key_bytes, public_key_bytes = generate_keypair()
private_key_b64 = base64.b64encode(private_key_bytes).decode()
public_key_b64 = base64.b64encode(public_key_bytes).decode()

# 2. Create event
event = {
    "event_id": "evt_001",
    "actor": "bp1_alice...",
    "type": "OBSERVATION",
    "subject": "x",
    "predicate": "p",
    "value": "hello",
    "timestamp_utc": "2024-02-17T16:00:00Z",
    "prev_event_hash": None,
}

# 3. Sign
signature = sign_event(event, private_key_b64)
event["signature"] = signature

# 4. Verify
is_valid = verify_event(event, public_key_b64)
assert is_valid, "Signature invalid!"

# 5. Hash for chain
event_hash = canonical_hash(event)

# 6. Create next event
next_event = {
    **event,
    "event_id": "evt_002",
    "prev_event_hash": event_hash,
    "value": "world",
}

# Sign and verify next event
next_signature = sign_event(next_event, private_key_b64)
next_event["signature"] = next_signature

assert verify_event(next_event, public_key_b64), "Next event invalid!"
```

## Key Rotation

See `rekey_backpack.py` for the key rotation protocol. The signing layer is the foundation; rotation is an event-layer operation.

## Performance

- **Key generation:** ~5ms (one-time)
- **Signing:** ~0.5ms per event
- **Verification:** ~0.5ms per event

For 1000 events: ~500ms total (signature validation in parallel).

## Security Considerations

1. **Private key protection** — Use env vars, HSM, or encrypted files. Never commit.
2. **Clock skew** — Timestamps are informational, not validation. Causal order verified by `prev_hash`.
3. **Replay attacks** — Prevented by causal chain. Same event signed twice has same signature (deterministic).

## References

- [RFC 8032: Edwards-Curve Digital Signature Algorithm (EdDSA)](https://tools.ietf.org/html/rfc8032)
- [Provara Protocol: Signing & Key Management](https://provara.dev/spec/)
