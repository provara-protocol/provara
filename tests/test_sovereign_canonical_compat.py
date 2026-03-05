"""Verify sovereign_schema uses provara.canonical_json, not its own copy."""

from provara.canonical_json import canonical_bytes, sha256_hex as cj_sha256
from provara.sovereign_schema import canonical_json, sha256_hex


def test_canonical_json_is_same_function():
    """Both modules produce identical bytes for the same input."""
    obj = {"z": 1, "a": [3, 2, 1], "m": {"nested": True}}
    assert canonical_json(obj) == canonical_bytes(obj)


def test_sha256_hex_matches():
    """Both sha256_hex functions produce identical digests."""
    data = b"test data for hashing"
    assert sha256_hex(data) == cj_sha256(data)
