"""
canonical_json.py — Backpack v1.0
Deterministic JSON canonicalization for content-addressed hashing.

Implements JCS-like canonical form (reference: RFC 8785):
- UTF-8 encoding
- Object keys sorted lexicographically by Unicode codepoint
- No insignificant whitespace
- Numbers: Python json module defaults for finite int/float
  (cross-language note: for byte-exact interop, prefer integer
   encoding or string-wrapped decimals for fractional values)
- No NaN/Infinity (raises ValueError)

IMPORTANT: All implementations of Backpack readers/writers MUST produce
identical canonical bytes for identical logical objects. Test with the
determinism_test fixture before shipping any new language binding.
"""

from __future__ import annotations
import hashlib
import json
from typing import Any


def canonical_dumps(obj: Any) -> str:
    """Return canonical JSON string with sorted keys and no whitespace."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_bytes(obj: Any) -> bytes:
    """Return canonical JSON as UTF-8 bytes."""
    return canonical_dumps(obj).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return lowercase hex SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def canonical_hash(obj: Any) -> str:
    """Return SHA-256 hex digest of canonical JSON bytes."""
    return sha256_hex(canonical_bytes(obj))
