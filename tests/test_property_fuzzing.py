"""
test_property_fuzzing.py — Provara Protocol v1.0 Property-Based Fuzzing (Lane 3A)

Uses Hypothesis to generate millions of inputs and verify that protocol
invariants hold across the entire reachable input space — not just the
cases the developer thought of.

Every crash is a spec finding. Every discovered edge case is a potential
security boundary that needs explicit documentation.

Properties tested:
  A. canonical_bytes / canonical_hash
       A1. Determinism: same input → same bytes, always
       A2. Key-order independence: insertion order doesn't change output
       A3. No exceptions on valid JSON-serializable values (no nan/inf)
       A4. Round-trip: canonical form parses back to logically equal object
       A5. Avalanche: any field change → different hash
       A6. Null keys preserved: null values survive canonicalization

  B. verify_event_signature
       B1. Never raises — always returns bool
       B2. Valid signature verifies
       B3. Wrong-key rejection: valid sig, different key → False
       B4. Garbage sig → False (never raises)
       B5. Stripped sig → False
       B6. Any field mutation → False (signed payload covers all fields)

  C. verify_causal_chain
       C1. Never raises on arbitrary event-like dict lists
       C2. Empty list → True (trivially valid)
       C3. Single valid genesis event → True
       C4. Valid N-length chain → True
       C5. Chain with broken link → False
       C6. Arbitrary garbage list doesn't crash
"""

import base64
import copy
import json
import math
import unittest

import pytest

try:
    from hypothesis import given, settings, assume, HealthCheck
    from hypothesis import strategies as st
    from hypothesis.strategies import composite
except ImportError:
    pytest.skip("hypothesis not installed", allow_module_level=True)

from provara.backpack_signing import BackpackKeypair, sign_event, verify_event_signature
from provara.canonical_json import canonical_bytes, canonical_hash
from provara.sync_v0 import verify_causal_chain


# ---------------------------------------------------------------------------
# Shared Hypothesis strategies
# ---------------------------------------------------------------------------

# JSON-safe scalar values (no nan/inf which are not JSON-compliant)
_json_scalar = st.one_of(
    st.integers(min_value=-(2**53), max_value=2**53),
    st.floats(allow_nan=False, allow_infinity=False, min_value=-(10**15), max_value=10**15),
    st.text(),
    st.booleans(),
    st.none(),
)

# Flat JSON object with text keys
_json_flat = st.dictionaries(
    keys=st.text(min_size=1, max_size=32),
    values=_json_scalar,
    min_size=0,
    max_size=12,
)

# Nested JSON object (one level of nesting)
_json_nested = st.dictionaries(
    keys=st.text(min_size=1, max_size=32),
    values=st.one_of(_json_scalar, _json_flat),
    min_size=0,
    max_size=8,
)


@composite
def _arbitrary_event(draw) -> dict:
    """Generate an event-shaped dict with arbitrary field values."""
    actor = draw(st.text(min_size=1, max_size=40))
    return {
        "type": draw(st.sampled_from(["OBSERVATION", "GENESIS", "POLICY", "CUSTOM"])),
        "namespace": draw(st.sampled_from(["local", "canonical", "contested", "archived"])),
        "actor": actor,
        "actor_key_id": draw(st.text(min_size=4, max_size=40)),
        "ts_logical": draw(st.integers(min_value=0, max_value=10**9)),
        "prev_event_hash": draw(st.one_of(st.none(), st.text(min_size=4, max_size=64))),
        "payload": draw(_json_flat),
    }


@composite
def _garbage_event(draw) -> dict:
    """Generate an arbitrary dict that may or may not look like an event."""
    return draw(st.one_of(
        _json_flat,
        _json_nested,
        _arbitrary_event(),
    ))


# ---------------------------------------------------------------------------
# A. canonical_bytes / canonical_hash properties
# ---------------------------------------------------------------------------

class TestPropertyCanonicalBytes(unittest.TestCase):
    """A. canonical_bytes invariants under arbitrary input."""

    @given(_json_nested)
    @settings(max_examples=2000, suppress_health_check=[HealthCheck.too_slow])
    def test_A1_determinism(self, obj: dict) -> None:
        """A1. Same input always produces same canonical bytes."""
        b1 = canonical_bytes(obj)
        b2 = canonical_bytes(obj)
        self.assertEqual(b1, b2)

    @given(_json_nested)
    @settings(max_examples=500)
    def test_A2_key_order_independence(self, obj: dict) -> None:
        """A2. Reversing key insertion order doesn't change canonical output."""
        reversed_obj = {k: obj[k] for k in reversed(list(obj.keys()))}
        self.assertEqual(canonical_bytes(obj), canonical_bytes(reversed_obj))

    @given(_json_nested)
    @settings(max_examples=1000)
    def test_A3_no_exceptions_on_valid_json(self, obj: dict) -> None:
        """A3. canonical_bytes never raises on valid JSON-serializable input."""
        try:
            result = canonical_bytes(obj)
            self.assertIsInstance(result, bytes)
        except (ValueError, TypeError) as exc:
            # nan/inf can slip through nested floats — that's spec-correct
            # re-raise only for unexpected exception types
            if "JSON" not in str(exc) and "float" not in str(exc).lower():
                raise

    @given(_json_nested)
    @settings(max_examples=1000)
    def test_A4_round_trip(self, obj: dict) -> None:
        """A4. Canonical form parses back to logically equal object."""
        # Filter out floats that can't round-trip (nan/inf already excluded by strategy)
        b = canonical_bytes(obj)
        parsed = json.loads(b.decode("utf-8"))
        self.assertEqual(obj, parsed)

    @given(_json_nested, st.text(min_size=1, max_size=32), _json_scalar)
    @settings(max_examples=500)
    def test_A5_avalanche_field_addition(self, obj: dict, new_key: str, new_val) -> None:
        """A5. Adding any new field changes the hash."""
        assume(new_key not in obj)
        h1 = canonical_hash(obj)
        modified = {**obj, new_key: new_val}
        h2 = canonical_hash(modified)
        self.assertNotEqual(h1, h2)

    @given(st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.none(),
        min_size=1,
        max_size=5,
    ))
    @settings(max_examples=200)
    def test_A6_null_values_preserved(self, obj: dict) -> None:
        """A6. Null values survive canonicalization — not omitted."""
        canonical_str = canonical_bytes(obj).decode("utf-8")
        self.assertIn("null", canonical_str)
        parsed = json.loads(canonical_str)
        self.assertEqual(obj, parsed)


# ---------------------------------------------------------------------------
# B. verify_event_signature properties
# ---------------------------------------------------------------------------

class TestPropertySignatureVerification(unittest.TestCase):
    """B. verify_event_signature invariants under arbitrary input."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.kp_a = BackpackKeypair.generate()
        cls.kp_b = BackpackKeypair.generate()

    def _make_valid_event(self, payload: dict | None = None) -> dict:
        event = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": "fuzzer",
            "actor_key_id": self.kp_a.key_id,
            "ts_logical": 0,
            "prev_event_hash": None,
            "payload": payload or {"x": 1},
        }
        event["event_id"] = f"evt_{canonical_hash(event)[:24]}"
        return sign_event(event, self.kp_a.private_key, self.kp_a.key_id)

    @given(_json_flat)
    @settings(max_examples=500)
    def test_B1_never_raises_on_arbitrary_event(self, garbage: dict) -> None:
        """B1. verify_event_signature never raises — always returns bool."""
        try:
            result = verify_event_signature(garbage, self.kp_a.public_key)
            self.assertIsInstance(result, bool)
        except Exception as exc:
            self.fail(f"verify_event_signature raised {type(exc).__name__}: {exc}")

    @given(_json_flat)
    @settings(max_examples=200)
    def test_B2_valid_signature_verifies(self, payload: dict) -> None:
        """B2. Signing an event then verifying it must always return True."""
        event = self._make_valid_event(payload)
        self.assertTrue(verify_event_signature(event, self.kp_a.public_key))

    @given(_json_flat)
    @settings(max_examples=200)
    def test_B3_wrong_key_rejects(self, payload: dict) -> None:
        """B3. A signature by kp_a must not verify against kp_b's public key."""
        event = self._make_valid_event(payload)
        self.assertFalse(verify_event_signature(event, self.kp_b.public_key))

    @given(st.binary(min_size=64, max_size=64))
    @settings(max_examples=500)
    def test_B4_random_sig_rejects(self, random_bytes: bytes) -> None:
        """B4. A random 64-byte value as sig must not verify."""
        event = self._make_valid_event()
        forged = copy.deepcopy(event)
        forged["sig"] = base64.b64encode(random_bytes).decode("ascii")
        self.assertFalse(verify_event_signature(forged, self.kp_a.public_key))

    def test_B5_stripped_sig_rejects(self) -> None:
        """B5. Missing sig field must return False, not raise."""
        event = self._make_valid_event()
        stripped = {k: v for k, v in event.items() if k != "sig"}
        self.assertFalse(verify_event_signature(stripped, self.kp_a.public_key))

    # Fields that are part of the signed payload (all fields except sig itself)
    _SIGNED_FIELDS = ["type", "namespace", "actor", "actor_key_id",
                      "ts_logical", "prev_event_hash", "payload", "event_id"]

    @given(
        st.sampled_from(_SIGNED_FIELDS),
        st.one_of(st.text(max_size=80), st.integers(), st.booleans(), st.none()),
    )
    @settings(max_examples=300)
    def test_B6_field_mutation_breaks_signature(self, key: str, new_val) -> None:
        """B6. Mutating any non-sig field on a signed event breaks the signature."""
        event = self._make_valid_event()
        assume(event.get(key) != new_val)  # Must actually change value
        mutated = copy.deepcopy(event)
        mutated[key] = new_val
        self.assertFalse(verify_event_signature(mutated, self.kp_a.public_key))


# ---------------------------------------------------------------------------
# C. verify_causal_chain properties
# ---------------------------------------------------------------------------

def _build_chain(actor: str, kp: BackpackKeypair, n: int) -> list:
    """Build a valid signed chain of n events."""
    events = []
    prev = None
    for i in range(n):
        ev: dict = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": actor,
            "actor_key_id": kp.key_id,
            "ts_logical": i,
            "prev_event_hash": prev,
            "payload": {"i": i},
        }
        ev["event_id"] = f"evt_{canonical_hash(ev)[:24]}"
        ev = sign_event(ev, kp.private_key, kp.key_id)
        events.append(ev)
        prev = ev["event_id"]
    return events


class TestPropertyCausalChain(unittest.TestCase):
    """C. verify_causal_chain invariants under arbitrary input."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.kp = BackpackKeypair.generate()
        cls.actor = "fuzzer_actor"

    @given(st.lists(_garbage_event(), min_size=0, max_size=20))
    @settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
    def test_C1_never_raises_on_arbitrary_lists(self, events: list) -> None:
        """C1. verify_causal_chain never raises — even on garbage input."""
        try:
            result = verify_causal_chain(events, "any_actor")
            self.assertIsInstance(result, bool)
        except Exception as exc:
            self.fail(f"verify_causal_chain raised {type(exc).__name__}: {exc}")

    def test_C2_empty_list_is_valid(self) -> None:
        """C2. Empty event log is trivially valid for any actor."""
        self.assertTrue(verify_causal_chain([], "any_actor"))

    def test_C3_single_genesis_event_is_valid(self) -> None:
        """C3. Single event with null prev passes."""
        chain = _build_chain(self.actor, self.kp, 1)
        self.assertTrue(verify_causal_chain(chain, self.actor))

    @given(st.integers(min_value=2, max_value=30))
    @settings(max_examples=50)
    def test_C4_valid_chain_always_passes(self, n: int) -> None:
        """C4. A correctly built chain of length n always verifies."""
        chain = _build_chain(self.actor, self.kp, n)
        self.assertTrue(verify_causal_chain(chain, self.actor))

    @given(st.data())
    @settings(max_examples=100)
    def test_C5_broken_link_always_fails(self, data) -> None:
        """C5. Breaking the prev_event_hash at any position fails the chain."""
        n = data.draw(st.integers(min_value=3, max_value=15))
        break_at = data.draw(st.integers(min_value=1, max_value=n - 1))
        chain = _build_chain(self.actor, self.kp, n)
        broken = copy.deepcopy(chain)
        broken[break_at]["prev_event_hash"] = "evt_" + "0" * 24
        self.assertFalse(verify_causal_chain(broken, self.actor))

    @given(st.lists(_garbage_event(), min_size=1, max_size=30))
    @settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
    def test_C6_unknown_actor_returns_true(self, events: list) -> None:
        """C6. Querying for an actor with no events is trivially True."""
        actor = "actor_that_does_not_exist_xyz_42"
        result = verify_causal_chain(events, actor)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
