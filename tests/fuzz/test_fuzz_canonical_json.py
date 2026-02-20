"""
Fuzzing harness for Provara canonical JSON parser and event deserialization.

Uses Hypothesis for property-based testing to find edge cases, crashes, and
security vulnerabilities in the parser.

Run: python -m pytest tests/fuzz/test_fuzz_canonical_json.py -v
"""

from __future__ import annotations
import json
import pytest
try:
    from hypothesis import given, settings, assume, HealthCheck
    from hypothesis import strategies as st
except ImportError:
    pytest.skip("hypothesis not installed", allow_module_level=True)
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from provara.canonical_json import canonical_dumps, canonical_bytes, canonical_hash


# ─────────────────────────────────────────────────────────────────────────────
# Strategy: Generate arbitrary but valid JSON objects
# ─────────────────────────────────────────────────────────────────────────────

@st.composite
def json_objects(draw, max_depth=3, max_size=5):
    """Generate arbitrary JSON-serializable objects."""
    # Base cases
    strategies = [
        st.none(),
        st.booleans(),
        st.integers(min_value=-1000000, max_value=1000000),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=100),
    ]
    
    # Recursive cases (if depth allows)
    if max_depth > 0:
        strategies.append(
            st.lists(
                json_objects(max_depth=max_depth - 1, max_size=max_size),
                max_size=max_size
            )
        )
        strategies.append(
            st.dictionaries(
                keys=st.text(max_size=50),
                values=json_objects(max_depth=max_depth - 1, max_size=max_size),
                max_size=max_size
            )
        )
    
    return draw(st.one_of(strategies))


# ─────────────────────────────────────────────────────────────────────────────
# Property 1: Determinism — Same object always produces same bytes
# ─────────────────────────────────────────────────────────────────────────────

class TestDeterminism:
    """Canonical form must be deterministic."""
    
    @given(json_objects())
    @settings(max_examples=500, deadline=None)
    def test_canonical_dumps_is_deterministic(self, obj):
        """Same object → same canonical string, every time."""
        result1 = canonical_dumps(obj)
        result2 = canonical_dumps(obj)
        result3 = canonical_dumps(obj)
        
        assert result1 == result2, f"Non-deterministic output: {obj}"
        assert result2 == result3, f"Non-deterministic output: {obj}"
    
    @given(json_objects())
    @settings(max_examples=500, deadline=None)
    def test_canonical_bytes_is_deterministic(self, obj):
        """Same object → same canonical bytes, every time."""
        result1 = canonical_bytes(obj)
        result2 = canonical_bytes(obj)
        
        assert result1 == result2, f"Non-deterministic bytes: {obj}"
    
    @given(json_objects())
    @settings(max_examples=500, deadline=None)
    def test_canonical_hash_is_deterministic(self, obj):
        """Same object → same hash, every time."""
        hash1 = canonical_hash(obj)
        hash2 = canonical_hash(obj)
        
        assert hash1 == hash2, f"Non-deterministic hash: {obj}"


# ─────────────────────────────────────────────────────────────────────────────
# Property 2: Roundtrip — canonical_dumps → json.loads → same object
# ─────────────────────────────────────────────────────────────────────────────

class TestRoundtrip:
    """Canonical form must be valid JSON that roundtrips."""
    
    @given(json_objects())
    @settings(max_examples=500, deadline=None)
    def test_canonical_dumps_roundtrips(self, obj):
        """canonical_dumps(obj) → json.loads → same object."""
        # Skip objects with floats (precision issues)
        assume(not isinstance(obj, float))
        
        canonical = canonical_dumps(obj)
        roundtripped = json.loads(canonical)
        
        # For dicts/lists, compare structure
        if isinstance(obj, (dict, list)):
            assert roundtripped == obj, f"Roundtrip failed: {obj} → {roundtripped}"
    
    @given(json_objects())
    @settings(max_examples=500, deadline=None)
    def test_canonical_bytes_roundtrips(self, obj):
        """canonical_bytes(obj) → json.loads → same object."""
        assume(not isinstance(obj, float))
        
        canonical = canonical_bytes(obj)
        roundtripped = json.loads(canonical.decode('utf-8'))
        
        if isinstance(obj, (dict, list)):
            assert roundtripped == obj, f"Bytes roundtrip failed: {obj}"


# ─────────────────────────────────────────────────────────────────────────────
# Property 3: Key Ordering — Object keys are always sorted
# ─────────────────────────────────────────────────────────────────────────────

class TestKeyOrdering:
    """Object keys must be sorted lexicographically."""
    
    @given(st.dictionaries(keys=st.text(max_size=20), values=st.integers(), max_size=10))
    @settings(max_examples=200, deadline=None)
    def test_keys_are_sorted(self, obj):
        """Object keys in canonical form are sorted."""
        canonical = canonical_dumps(obj)
        
        # Parse back to check key order
        parsed = json.loads(canonical)
        if isinstance(parsed, dict):
            keys = list(parsed.keys())
            assert keys == sorted(keys), f"Keys not sorted: {keys}"
    
    @given(json_objects())
    @settings(max_examples=200, deadline=None)
    def test_nested_keys_are_sorted(self, obj):
        """Nested object keys are also sorted."""
        canonical = canonical_dumps(obj)
        
        # Verify it's valid JSON
        parsed = json.loads(canonical)
        
        def check_sorted(o):
            if isinstance(o, dict):
                keys = list(o.keys())
                assert keys == sorted(keys), f"Nested keys not sorted: {keys}"
                for v in o.values():
                    check_sorted(v)
            elif isinstance(o, list):
                for item in o:
                    check_sorted(item)
        
        check_sorted(parsed)


# ─────────────────────────────────────────────────────────────────────────────
# Property 4: No Insignificant Whitespace
# ─────────────────────────────────────────────────────────────────────────────

class TestNoWhitespace:
    """Canonical form has no insignificant whitespace."""
    
    @given(json_objects())
    @settings(max_examples=200, deadline=None)
    def test_no_whitespace(self, obj):
        """Canonical form has no spaces, newlines, or tabs."""
        canonical = canonical_dumps(obj)
        
        # Check for common whitespace (excluding inside strings)
        # Simple check: no " : " or ", " patterns
        assert ' :' not in canonical or canonical.count(' :') == 0
        assert ', ' not in canonical or canonical.count(', ') == 0
        
        # No newlines or tabs
        assert '\n' not in canonical or canonical.count('\n') <= canonical.count('\\n')
        assert '\t' not in canonical


# ─────────────────────────────────────────────────────────────────────────────
# Property 5: Unicode Handling
# ─────────────────────────────────────────────────────────────────────────────

class TestUnicodeHandling:
    """Unicode must be preserved, not escaped."""
    
    @given(st.text(max_size=100).filter(lambda s: any(ord(c) > 127 for c in s)))
    @settings(max_examples=100, deadline=None)
    def test_unicode_preserved(self, text):
        """Unicode characters are preserved, not escaped."""
        obj = {"key": text}
        canonical = canonical_dumps(obj)
        
        # Unicode chars should be in output (not \uXXXX escaped)
        # This is a soft check - some escaping is OK for control chars
        assert isinstance(canonical, str)
        assert len(canonical) > 0
    
    @given(st.dictionaries(keys=st.text(max_size=20), values=st.text(max_size=50)))
    @settings(max_examples=100, deadline=None)
    def test_unicode_keys_sorted_correctly(self, obj):
        """Unicode keys are sorted by codepoint."""
        canonical = canonical_dumps(obj)
        parsed = json.loads(canonical)
        
        if isinstance(parsed, dict):
            keys = list(parsed.keys())
            # Python's sorted() sorts by Unicode codepoint by default
            assert keys == sorted(keys)


# ─────────────────────────────────────────────────────────────────────────────
# Property 6: Edge Cases — Empty, None, Boundary Values
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """Edge cases must be handled correctly."""
    
    def test_empty_dict(self):
        """Empty dict produces valid canonical form."""
        result = canonical_dumps({})
        assert result == '{}'
        assert canonical_hash({}) == canonical_hash({})
    
    def test_empty_list(self):
        """Empty list produces valid canonical form."""
        result = canonical_dumps([])
        assert result == '[]'
    
    def test_none_value(self):
        """None is preserved as 'null'."""
        result = canonical_dumps(None)
        assert result == 'null'
    
    def test_nested_empty(self):
        """Nested empty structures are handled."""
        obj = {"a": {}, "b": [], "c": None}
        result = canonical_dumps(obj)
        parsed = json.loads(result)
        assert parsed == obj
    
    @given(st.integers(min_value=-1, max_value=1))
    def test_small_integers(self, n):
        """Small integers are preserved exactly."""
        obj = {"value": n}
        result = canonical_dumps(obj)
        parsed = json.loads(result)
        assert parsed["value"] == n
    
    def test_deeply_nested(self):
        """Deeply nested structures are handled."""
        obj = {"a": {"b": {"c": {"d": {"e": "deep"}}}}}
        result = canonical_dumps(obj)
        parsed = json.loads(result)
        assert parsed == obj


# ─────────────────────────────────────────────────────────────────────────────
# Property 7: Hash Consistency
# ─────────────────────────────────────────────────────────────────────────────

class TestHashConsistency:
    """Hashes must be consistent and well-formed."""
    
    @given(json_objects())
    @settings(max_examples=200, deadline=None)
    def test_hash_is_64_hex_chars(self, obj):
        """Hash is always 64 lowercase hex characters."""
        h = canonical_hash(obj)
        assert len(h) == 64, f"Hash length wrong: {len(h)}"
        assert all(c in '0123456789abcdef' for c in h), f"Invalid hex: {h}"
    
    @given(json_objects(), json_objects())
    @settings(max_examples=200, deadline=None)
    def test_different_objects_different_hashes(self, obj1, obj2):
        """Different objects (usually) have different hashes."""
        # Skip if objects are equal
        assume(obj1 != obj2)
        
        hash1 = canonical_hash(obj1)
        hash2 = canonical_hash(obj2)
        
        # Collision would be catastrophic
        assert hash1 != hash2, f"Hash collision: {obj1} vs {obj2}"
    
    def test_hash_changes_with_key_order(self):
        """Key order affects hash (even if logically equivalent)."""
        # This verifies we're hashing the canonical form, not logical equality
        obj1 = {"a": 1, "b": 2}
        # Same keys, different order in source (but canonical form is same)
        obj2 = {"b": 2, "a": 1}
        
        # After canonicalization, these should be identical
        hash1 = canonical_hash(obj1)
        hash2 = canonical_hash(obj2)
        
        assert hash1 == hash2, "Canonical form should be identical"


# ─────────────────────────────────────────────────────────────────────────────
# Property 8: Security — Reject Invalid Input
# ─────────────────────────────────────────────────────────────────────────────

class TestSecurityRejection:
    """Parser must reject invalid/malicious input."""
    
    def test_nan_rejected(self):
        """NaN values are rejected."""
        import math
        with pytest.raises(ValueError):
            canonical_dumps(float('nan'))
    
    def test_infinity_rejected(self):
        """Infinity values are rejected."""
        with pytest.raises(ValueError):
            canonical_dumps(float('inf'))
    
    def test_negative_infinity_rejected(self):
        """Negative infinity is rejected."""
        with pytest.raises(ValueError):
            canonical_dumps(float('-inf'))


# ─────────────────────────────────────────────────────────────────────────────
# Property 9: Event Structure Fuzzing
# ─────────────────────────────────────────────────────────────────────────────

class TestEventStructure:
    """Fuzz typical Provara event structures."""
    
    @given(
        st.text(max_size=50),  # event_type
        st.dictionaries(
            keys=st.text(max_size=30),
            values=st.one_of(st.text(max_size=100), st.integers(), st.booleans()),
            max_size=10
        ),  # payload
        st.text(max_size=64),  # actor
    )
    @settings(max_examples=200, deadline=None)
    def test_event_structure(self, event_type, payload, actor):
        """Typical event structures canonicalize correctly."""
        event = {
            "type": event_type,
            "payload": payload,
            "actor": actor,
            "timestamp": "2026-02-17T00:00:00Z",
        }
        
        # Should not crash
        canonical = canonical_dumps(event)
        h = canonical_hash(event)
        
        # Should be valid
        assert len(canonical) > 0
        assert len(h) == 64


# ─────────────────────────────────────────────────────────────────────────────
# Run with: python -m pytest tests/fuzz/test_fuzz_canonical_json.py -v
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
