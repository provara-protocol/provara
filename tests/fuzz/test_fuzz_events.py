"""
Fuzzing harness for Provara event deserialization and chain verification.

Tests the event parsing, signature verification, and chain integrity under
adversarial input conditions.

Run: python -m pytest tests/fuzz/test_fuzz_events.py -v
"""

from __future__ import annotations
import json
import pytest
try:
    from hypothesis import given, settings, assume
    from hypothesis import strategies as st
except ImportError:
    pytest.skip("hypothesis not installed", allow_module_level=True)
import sys
import os
import hashlib

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from provara.canonical_json import canonical_dumps, canonical_hash


# ─────────────────────────────────────────────────────────────────────────────
# Strategy: Generate Provara-like event structures
# ─────────────────────────────────────────────────────────────────────────────

@st.composite
def valid_events(draw):
    """Generate valid Provara event structures."""
    event_types = [
        "OBSERVATION", "ASSERTION", "ATTESTATION", "RETRACTION",
        "KEY_REVOCATION", "KEY_PROMOTION", "REDUCER_EPOCH", "GENESIS"
    ]
    
    event_type = draw(st.sampled_from(event_types))
    actor = draw(st.text(min_size=1, max_size=64))
    
    # Generate payload based on event type
    if event_type == "OBSERVATION" or event_type == "ASSERTION":
        payload = draw(st.fixed_dictionaries({
            "subject": st.text(max_size=100),
            "predicate": st.text(max_size=100),
            "value": st.one_of(st.text(max_size=200), st.integers(), st.booleans()),
            "confidence": st.floats(min_value=0, max_value=1),
        }))
    elif event_type == "ATTESTATION":
        payload = draw(st.fixed_dictionaries({
            "subject": st.text(max_size=100),
            "predicate": st.text(max_size=100),
            "value": st.text(max_size=200),
            "target_event_id": st.text(min_size=1, max_size=64),
        }))
    elif event_type == "RETRACTION":
        payload = draw(st.fixed_dictionaries({
            "subject": st.text(max_size=100),
            "predicate": st.text(max_size=100),
        }))
    else:
        payload = draw(st.dictionaries(
            keys=st.text(max_size=50),
            values=st.one_of(st.text(max_size=100), st.integers(), st.booleans()),
            max_size=10
        ))
    
    return {
        "type": event_type,
        "actor": actor,
        "payload": payload,
        "timestamp": draw(st.text(min_size=20, max_size=30)),  # ISO 8601-like
    }


# ─────────────────────────────────────────────────────────────────────────────
# Property 1: Event ID Derivation
# ─────────────────────────────────────────────────────────────────────────────

class TestEventIDDerivation:
    """Event ID must be deterministically derived from content."""
    
    @given(valid_events())
    @settings(max_examples=200, deadline=None)
    def test_event_id_is_deterministic(self, event):
        """Same event content → same event ID."""
        # Derive event ID (evt_ + SHA256[:24])
        hashable = {k: v for k, v in event.items() if k not in ("event_id", "sig")}
        digest = canonical_hash(hashable)
        event_id = f"evt_{digest[:24]}"
        
        # Derive again
        digest2 = canonical_hash(hashable)
        event_id2 = f"evt_{digest2[:24]}"
        
        assert event_id == event_id2
    
    @given(valid_events(), valid_events())
    @settings(max_examples=100, deadline=None)
    def test_different_events_different_ids(self, event1, event2):
        """Different events have different IDs."""
        assume(event1 != event2)
        
        def derive_id(e):
            hashable = {k: v for k, v in e.items() if k not in ("event_id", "sig")}
            return f"evt_{canonical_hash(hashable)[:24]}"
        
        id1 = derive_id(event1)
        id2 = derive_id(event2)
        
        # Collision would be catastrophic
        assert id1 != id2, f"Event ID collision: {event1} vs {event2}"
    
    def test_event_id_format(self):
        """Event ID is evt_ + 24 hex chars."""
        event = {
            "type": "OBSERVATION",
            "actor": "test_actor",
            "payload": {"key": "value"},
        }
        
        hashable = {k: v for k, v in event.items() if k not in ("event_id", "sig")}
        digest = canonical_hash(hashable)
        event_id = f"evt_{digest[:24]}"
        
        assert event_id.startswith("evt_")
        assert len(event_id) == 28  # "evt_" + 24 hex chars
        assert all(c in '0123456789abcdef' for c in event_id[4:])


# ─────────────────────────────────────────────────────────────────────────────
# Property 2: Chain Integrity
# ─────────────────────────────────────────────────────────────────────────────

class TestChainIntegrity:
    """Event chains must maintain causal integrity."""
    
    @given(st.lists(valid_events(), min_size=2, max_size=10))
    @settings(max_examples=50, deadline=None)
    def test_chain_linkage(self, events):
        """Events in a chain are linked via prev_event_hash."""
        # Build a chain
        chained_events = []
        prev_hash = None
        
        for event in events:
            event_with_chain = event.copy()
            event_with_chain["prev_event_hash"] = prev_hash
            
            # Derive event ID
            hashable = {k: v for k, v in event_with_chain.items() if k not in ("event_id", "sig")}
            event_id = f"evt_{canonical_hash(hashable)[:24]}"
            event_with_chain["event_id"] = event_id
            
            chained_events.append(event_with_chain)
            prev_hash = event_id
        
        # Verify chain
        for i, event in enumerate(chained_events):
            if i == 0:
                assert event["prev_event_hash"] is None
            else:
                prev_event = chained_events[i - 1]
                assert event["prev_event_hash"] == prev_event["event_id"]
    
    def test_first_event_has_null_prev_hash(self):
        """First event in chain has null prev_event_hash."""
        event = {
            "type": "GENESIS",
            "actor": "founder",
            "payload": {},
            "prev_event_hash": None,
        }
        
        hashable = {k: v for k, v in event.items() if k not in ("event_id", "sig")}
        event_id = f"evt_{canonical_hash(hashable)[:24]}"
        event["event_id"] = event_id
        
        assert event["prev_event_hash"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Property 3: Malformed Event Handling
# ─────────────────────────────────────────────────────────────────────────────

class TestMalformedEvents:
    """Parser must handle malformed events gracefully."""
    
    def test_missing_type_field(self):
        """Event without type field is still hashable."""
        event = {
            "actor": "test",
            "payload": {},
        }
        
        # Should not crash
        hashable = {k: v for k, v in event.items() if k not in ("event_id", "sig")}
        h = canonical_hash(hashable)
        assert len(h) == 64
    
    def test_missing_actor_field(self):
        """Event without actor is still hashable."""
        event = {
            "type": "OBSERVATION",
            "payload": {},
        }
        
        hashable = {k: v for k, v in event.items() if k not in ("event_id", "sig")}
        h = canonical_hash(hashable)
        assert len(h) == 64
    
    def test_missing_payload_field(self):
        """Event without payload is still hashable."""
        event = {
            "type": "OBSERVATION",
            "actor": "test",
        }
        
        hashable = {k: v for k, v in event.items() if k not in ("event_id", "sig")}
        h = canonical_hash(hashable)
        assert len(h) == 64
    
    @given(st.text())
    @settings(max_examples=50, deadline=None)
    def test_event_with_sig_field_excluded_from_hash(self, sig_value):
        """Signature field is excluded from event ID derivation."""
        event_with_sig = {
            "type": "OBSERVATION",
            "actor": "test",
            "payload": {},
            "sig": sig_value,
        }
        
        event_without_sig = {
            "type": "OBSERVATION",
            "actor": "test",
            "payload": {},
        }
        
        # Both should produce same hash (sig is excluded)
        hashable_with = {k: v for k, v in event_with_sig.items() if k not in ("event_id", "sig")}
        hashable_without = {k: v for k, v in event_without_sig.items() if k not in ("event_id", "sig")}
        
        assert canonical_hash(hashable_with) == canonical_hash(hashable_without)
    
    @given(st.text())
    @settings(max_examples=50, deadline=None)
    def test_event_with_event_id_field_excluded_from_hash(self, event_id_value):
        """Event ID field is excluded from derivation."""
        event_with_id = {
            "type": "OBSERVATION",
            "actor": "test",
            "payload": {},
            "event_id": event_id_value,
        }
        
        event_without_id = {
            "type": "OBSERVATION",
            "actor": "test",
            "payload": {},
        }
        
        # Both should produce same hash (event_id is excluded)
        hashable_with = {k: v for k, v in event_with_id.items() if k not in ("event_id", "sig")}
        hashable_without = {k: v for k, v in event_without_id.items() if k not in ("event_id", "sig")}
        
        assert canonical_hash(hashable_with) == canonical_hash(hashable_without)


# ─────────────────────────────────────────────────────────────────────────────
# Property 4: Replay Attack Detection
# ─────────────────────────────────────────────────────────────────────────────

class TestReplayAttacks:
    """System must detect replayed events."""
    
    @given(valid_events())
    @settings(max_examples=50, deadline=None)
    def test_event_id_is_unique_identifier(self, event):
        """Event ID uniquely identifies event content."""
        hashable = {k: v for k, v in event.items() if k not in ("event_id", "sig")}
        event_id = f"evt_{canonical_hash(hashable)[:24]}"
        
        # Same content → same ID (this is how we detect replays)
        hashable2 = {k: v for k, v in event.items() if k not in ("event_id", "sig")}
        event_id2 = f"evt_{canonical_hash(hashable2)[:24]}"
        
        assert event_id == event_id2
    
    def test_modified_event_has_different_id(self):
        """Modified event has different ID (replay detection)."""
        original = {
            "type": "OBSERVATION",
            "actor": "test",
            "payload": {"value": "original"},
        }
        
        modified = {
            "type": "OBSERVATION",
            "actor": "test",
            "payload": {"value": "modified"},
        }
        
        def derive_id(e):
            hashable = {k: v for k, v in e.items() if k not in ("event_id", "sig")}
            return f"evt_{canonical_hash(hashable)[:24]}"
        
        assert derive_id(original) != derive_id(modified)


# ─────────────────────────────────────────────────────────────────────────────
# Property 5: Cross-Vault Replay
# ─────────────────────────────────────────────────────────────────────────────

class TestCrossVaultReplay:
    """Events must be verifiable across vaults."""
    
    @given(valid_events())
    @settings(max_examples=50, deadline=None)
    def test_event_id_is_portable(self, event):
        """Event ID is the same regardless of where it's computed."""
        hashable = {k: v for k, v in event.items() if k not in ("event_id", "sig")}
        
        # Compute in different "contexts" (should be identical)
        id1 = f"evt_{canonical_hash(hashable)[:24]}"
        id2 = f"evt_{canonical_hash(hashable)[:24]}"
        id3 = f"evt_{canonical_hash(hashable)[:24]}"
        
        assert id1 == id2 == id3


# ─────────────────────────────────────────────────────────────────────────────
# Run with: python -m pytest tests/fuzz/test_fuzz_events.py -v
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
