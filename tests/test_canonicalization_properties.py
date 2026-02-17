"""
test_canonicalization_properties.py — Canonical JSON Determinism Tests

Tests that canonical JSON serialization is deterministic and conforms to RFC 8785.

Run:
  PYTHONPATH=src pytest tests/test_canonicalization_properties.py -v
"""

import json
import unittest
from provara.canonical_json import canonical_bytes, canonical_dumps, canonical_hash


class TestCanonicalizationDeterminism(unittest.TestCase):
    """Property: Canonical JSON is deterministic."""

    def test_canonical_is_idempotent(self):
        """Canonical bytes must be identical on repeated calls."""
        data = {"name": "test", "value": 42, "items": [1, 2, 3]}
        
        bytes_1 = canonical_bytes(data)
        bytes_2 = canonical_bytes(data)
        
        self.assertEqual(bytes_1, bytes_2)

    def test_canonical_ignores_insertion_order(self):
        """Order of key insertion must not affect canonical bytes."""
        dict_a = {"z": 1, "a": 2, "m": 3}
        dict_b = {"a": 2, "m": 3, "z": 1}
        
        bytes_a = canonical_bytes(dict_a)
        bytes_b = canonical_bytes(dict_b)
        
        self.assertEqual(bytes_a, bytes_b)

    def test_canonical_sorts_keys_lexicographically(self):
        """Keys must be sorted in canonical output."""
        data = {"c": 3, "a": 1, "b": 2}
        canonical_str = canonical_dumps(data)
        
        # Should be in order: a, b, c
        self.assertTrue(canonical_str.index('"a"') < canonical_str.index('"b"'))
        self.assertTrue(canonical_str.index('"b"') < canonical_str.index('"c"'))

    def test_canonical_no_whitespace(self):
        """Canonical output must have no extraneous whitespace."""
        data = {"key": "value", "nested": {"inner": True}}
        canonical_str = canonical_dumps(data)
        
        # Should not contain spaces or newlines
        self.assertNotIn(" ", canonical_str)
        self.assertNotIn("\n", canonical_str)
        self.assertNotIn("\t", canonical_str)

    def test_canonical_preserves_nulls(self):
        """Null values must be preserved, not omitted."""
        data = {"present": 1, "absent": None}
        canonical_str = canonical_bytes(data).decode('utf-8')
        
        self.assertIn("null", canonical_str)

    def test_canonical_handles_numbers_correctly(self):
        """Numbers must be normalized (no leading zeros, +signs)."""
        test_cases = [
            ({"value": 0}, '{"value":0}'),
            ({"value": 1}, '{"value":1}'),
            ({"value": -1}, '{"value":-1}'),
            ({"value": 42}, '{"value":42}'),
        ]
        
        for data, expected in test_cases:
            canonical_str = canonical_dumps(data)
            self.assertEqual(canonical_str, expected)

    def test_canonical_empty_dict(self):
        """Empty dict should canonicalize to '{}'."""
        canonical_str = canonical_dumps({})
        self.assertEqual(canonical_str, "{}")

    def test_canonical_empty_list(self):
        """Empty list should canonicalize to '[]'."""
        data = {"items": []}
        canonical_str = canonical_dumps(data)
        self.assertEqual(canonical_str, '{"items":[]}')

    def test_canonical_nested_dicts(self):
        """Nested dicts with mixed keys should be sorted at each level."""
        data = {
            "z": {"nested_z": 1},
            "a": {"nested_a": 2},
        }
        canonical_str = canonical_dumps(data)
        
        # Outer keys: a before z
        self.assertTrue(canonical_str.index('"a"') < canonical_str.index('"z"'))

    def test_canonical_hash_deterministic(self):
        """Hash of identical objects must be identical."""
        data = {"test": 123, "array": [1, 2, 3]}
        
        hash_1 = canonical_hash(data)
        hash_2 = canonical_hash(data)
        
        self.assertEqual(hash_1, hash_2)

    def test_canonical_hash_changes_with_content(self):
        """Changing content must change hash."""
        data_1 = {"value": 1}
        data_2 = {"value": 2}
        
        hash_1 = canonical_hash(data_1)
        hash_2 = canonical_hash(data_2)
        
        self.assertNotEqual(hash_1, hash_2)

    def test_canonical_hash_is_lowercase_hex(self):
        """Hash output must be lowercase hex (64 chars)."""
        data = {"test": True}
        hash_str = canonical_hash(data)
        
        self.assertEqual(len(hash_str), 64)
        self.assertTrue(all(c in '0123456789abcdef' for c in hash_str))

    def test_canonical_unicode_handling(self):
        """Unicode strings must be handled correctly."""
        data = {"emoji": "🔐", "text": "hello"}
        canonical_str = canonical_dumps(data)
        
        # Should parse back to identical data
        parsed = json.loads(canonical_str)
        self.assertEqual(parsed["emoji"], "🔐")

    def test_canonical_array_ordering_preserved(self):
        """Arrays must preserve element order (not be re-sorted)."""
        data_1 = {"array": [3, 1, 2]}
        data_2 = {"array": [1, 2, 3]}
        
        bytes_1 = canonical_bytes(data_1)
        bytes_2 = canonical_bytes(data_2)
        
        # Different arrays should have different canonical form
        self.assertNotEqual(bytes_1, bytes_2)


if __name__ == "__main__":
    unittest.main()
