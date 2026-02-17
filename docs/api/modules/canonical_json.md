# canonical_json

**Module:** `src/provara/canonical_json.py`

Deterministic JSON canonicalization for content-addressed hashing. Implements RFC 8785 (JCS) canonical form.

## Overview

All cryptographic operations (hashing, signing, chain verification) operate on canonical JSON bytes. This ensures:

- **Determinism:** Same logical object always produces identical bytes
- **Portability:** Cross-language implementations produce identical hashes
- **Auditability:** Humans can verify hashes by hand if needed

## Canonical Form Rules

1. **UTF-8 encoding** — All strings encoded as UTF-8
2. **Sorted keys** — Object keys ordered lexicographically by Unicode codepoint
3. **No whitespace** — Compact separators (`","` and `":"`)
4. **No NaN/Infinity** — Raises `ValueError` if encountered
5. **Finite numbers** — Python `json` module defaults (cross-language note: prefer integer encoding or string-wrapped decimals for fractional values)

## Core Functions

### `canonical_dumps(obj: Any) -> str`

Return canonical JSON string with sorted keys and no whitespace.

```python
from provara.canonical_json import canonical_dumps

obj = {"name": "Alice", "age": 30}
canonical_str = canonical_dumps(obj)
# Returns: '{"age":30,"name":"Alice"}'
```

### `canonical_bytes(obj: Any) -> bytes`

Return canonical JSON as UTF-8 encoded bytes.

```python
from provara.canonical_json import canonical_bytes

obj = {"event_id": "evt_123", "timestamp": "2024-01-01T00:00:00Z"}
canonical_bytes(obj)
# Returns: b'{"event_id":"evt_123","timestamp":"2024-01-01T00:00:00Z"}'
```

### `sha256_hex(data: bytes) -> str`

Return lowercase hex SHA-256 digest of bytes.

```python
from provara.canonical_json import sha256_hex

data = b"some event data"
digest = sha256_hex(data)
# Returns: "3f4a..." (64-char hex string)
```

### `canonical_hash(obj: Any) -> str`

Return SHA-256 hex digest of canonical JSON bytes. **This is the primary function for event hashing.**

```python
from provara.canonical_json import canonical_hash

event = {
    "event_id": "evt_123",
    "actor": "alice",
    "timestamp": "2024-01-01T00:00:00Z"
}

event_hash = canonical_hash(event)
# Same event always produces same hash
```

## Security Notes

- Canonical form is **deterministic but not cryptographic proof**. It ensures reproducibility across implementations.
- Use `backpack_signing` for Ed25519 signatures over canonical bytes.
- Use `backpack_integrity` for Merkle tree hashing.

## Cross-Language Compatibility

Before shipping a Provara implementation in a new language:

1. Run the determinism test fixture: `test_vectors/vectors.json`
2. Verify that canonical JSON for each test vector produces the expected hash
3. If hashes diverge, reconcile JSON serialization order and numeric precision

## Example: Event Hashing

```python
from provara.canonical_json import canonical_hash

event = {
    "event_id": "evt_001",
    "actor": "bp1_alice...",
    "timestamp": "2024-02-17T16:00:00Z",
    "prev_event_hash": None,
    "type": "OBSERVATION",
    "payload": {"subject": "family_tree", "predicate": "child_of", "value": "John"},
    "confidence": 0.95,
}

# Chain forward reference
event_hash = canonical_hash(event)
next_event = {
    **event,
    "event_id": "evt_002",
    "prev_event_hash": event_hash,
}

next_hash = canonical_hash(next_event)
```

## Performance

Canonical JSON serialization is O(n) where n is object size. For typical events (< 10 KB), serialization + hashing takes < 1ms.

## References

- [RFC 8785: JSON Canonicalization Scheme](https://tools.ietf.org/html/rfc8785)
- [Provara Protocol Spec: Canonical JSON](https://provara.dev/spec/)
