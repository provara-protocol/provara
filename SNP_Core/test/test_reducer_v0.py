"""
test_reducer_v0.py — Backpack v1.0 Reducer Compliance Tests

Required by spec §12: A compliant implementation MUST pass:
  - determinism_test: replay same log twice → identical state hash
  - integrity_test: (in sync layer, not here)
  - merge_test: (in sync layer, not here)
  - lease_test: (in sync layer, not here)

Additional reducer-specific invariant tests:
  - contested lifecycle (observe → conflict → attest → resolve)
  - archived namespace (superseded canonical beliefs preserved)
  - agreeing evidence strengthens confidence (no downward overwrite)
  - malformed event resilience
  - unknown event type passthrough
  - namespace normalization
  - reducer epoch tracking
  - evidence grouping in contested records
  - idempotent replay (same events = same hash regardless of run count)
  - event ordering sensitivity (different order = potentially different state)

Run:
  python -m unittest test_reducer_v0 -v
"""

import unittest
import json
from reducer_v0 import SovereignReducerV0
from canonical_json import canonical_dumps, canonical_hash


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _obs(event_id, actor, subject, predicate, value, confidence=0.9, ts=None, ns="local"):
    return {
        "event_id": event_id,
        "type": "OBSERVATION",
        "namespace": ns,
        "actor": actor,
        "payload": {
            "subject": subject,
            "predicate": predicate,
            "value": value,
            "confidence": confidence,
            "timestamp": ts or "2026-02-12T19:30:00Z",
        },
    }


def _attest(event_id, actor, subject, predicate, value, target_event_id=None):
    return {
        "event_id": event_id,
        "type": "ATTESTATION",
        "namespace": "canonical",
        "actor": actor,
        "payload": {
            "subject": subject,
            "predicate": predicate,
            "value": value,
            "target_event_id": target_event_id,
            "actor_key_id": f"{actor}_key",
        },
    }


FIXTURE_EVENTS = [
    _obs("e1", "robot_a", "door_01", "opens", "inward", 0.9),
    _obs("e2", "robot_a", "door_01", "opens", "outward", 0.95,
         ts="2026-02-12T19:31:00Z"),
    _attest("e3", "archive_peer", "door_01", "opens", "outward", "e2"),
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeterminism(unittest.TestCase):
    """Spec §12 — determinism_test"""

    def test_byte_for_byte_determinism(self):
        """Same events → identical JSON output across two independent runs."""
        r1 = SovereignReducerV0()
        r1.apply_events(FIXTURE_EVENTS)
        out1 = r1.export_state_json()

        r2 = SovereignReducerV0()
        r2.apply_events(FIXTURE_EVENTS)
        out2 = r2.export_state_json()

        self.assertEqual(out1, out2, "Byte-identical output required")

    def test_idempotent_across_instances(self):
        """Creating N fresh instances with same input → same hash."""
        hashes = set()
        for _ in range(5):
            r = SovereignReducerV0()
            r.apply_events(FIXTURE_EVENTS)
            hashes.add(r.state["metadata"]["state_hash"])
        self.assertEqual(len(hashes), 1, "All runs must produce identical state hash")

    def test_state_hash_not_self_referential(self):
        """State hash should be independently computable without prior hash."""
        r = SovereignReducerV0()
        r.apply_events(FIXTURE_EVENTS[:1])
        hash1 = r.state["metadata"]["state_hash"]

        # Manually recompute — the hash should NOT depend on any prior state_hash
        r2 = SovereignReducerV0()
        r2.apply_events(FIXTURE_EVENTS[:1])
        hash2 = r2._compute_state_hash()

        self.assertEqual(hash1, hash2)


class TestContestedLifecycle(unittest.TestCase):
    """Core contested → attested lifecycle."""

    def test_observation_to_local(self):
        r = SovereignReducerV0()
        r.apply_event(FIXTURE_EVENTS[0])
        state = r.export_state()
        self.assertIn("door_01:opens", state["local"])
        self.assertEqual(state["contested"], {})
        self.assertEqual(state["canonical"], {})

    def test_conflicting_observation_to_contested(self):
        r = SovereignReducerV0()
        r.apply_event(FIXTURE_EVENTS[0])
        r.apply_event(FIXTURE_EVENTS[1])
        state = r.export_state()
        self.assertIn("door_01:opens", state["contested"])
        # Local should be cleaned when contested
        self.assertNotIn("door_01:opens", state["local"])

    def test_attestation_resolves_contested(self):
        r = SovereignReducerV0()
        r.apply_events(FIXTURE_EVENTS)
        state = r.export_state()
        self.assertIn("door_01:opens", state["canonical"])
        self.assertNotIn("door_01:opens", state["contested"])
        self.assertNotIn("door_01:opens", state["local"])
        self.assertEqual(state["canonical"]["door_01:opens"]["value"], "outward")

    def test_contested_captures_all_evidence(self):
        """Contested record should include evidence for ALL observed values."""
        r = SovereignReducerV0()
        r.apply_event(FIXTURE_EVENTS[0])  # inward, 0.9
        r.apply_event(FIXTURE_EVENTS[1])  # outward, 0.95
        state = r.export_state()

        contested = state["contested"]["door_01:opens"]
        evidence_groups = contested["evidence_by_value"]
        self.assertEqual(contested["total_evidence_count"], 2)
        # Should have two groups (one per distinct value)
        self.assertEqual(len(evidence_groups), 2)


class TestArchivedNamespace(unittest.TestCase):
    """Superseded canonical beliefs move to archived/."""

    def test_superseded_canonical_archived(self):
        r = SovereignReducerV0()
        # First attestation: door opens inward
        r.apply_event(_attest("a1", "admin", "door_01", "opens", "inward"))
        self.assertEqual(r.state["canonical"]["door_01:opens"]["value"], "inward")

        # Second attestation: door opens outward (supersedes)
        r.apply_event(_attest("a2", "admin", "door_01", "opens", "outward"))
        self.assertEqual(r.state["canonical"]["door_01:opens"]["value"], "outward")

        # Archived should contain the old value
        archived = r.state["archived"].get("door_01:opens", [])
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0]["value"], "inward")
        self.assertEqual(archived[0]["superseded_by"], "a2")

    def test_multiple_supersessions(self):
        """Three successive attestations → two archived entries."""
        r = SovereignReducerV0()
        r.apply_event(_attest("a1", "admin", "door_01", "opens", "inward"))
        r.apply_event(_attest("a2", "admin", "door_01", "opens", "outward"))
        r.apply_event(_attest("a3", "admin", "door_01", "opens", "sliding"))

        self.assertEqual(r.state["canonical"]["door_01:opens"]["value"], "sliding")
        archived = r.state["archived"]["door_01:opens"]
        self.assertEqual(len(archived), 2)
        self.assertEqual(archived[0]["value"], "inward")
        self.assertEqual(archived[1]["value"], "outward")


class TestConfidenceHandling(unittest.TestCase):
    """Agreeing evidence should strengthen, not overwrite downward."""

    def test_agreeing_evidence_keeps_max_confidence(self):
        r = SovereignReducerV0()
        r.apply_event(_obs("e1", "robot_a", "mug", "color", "red", confidence=0.9))
        r.apply_event(_obs("e2", "robot_b", "mug", "color", "red", confidence=0.4))

        local = r.state["local"]["mug:color"]
        # Should retain 0.9, not overwrite to 0.4
        self.assertEqual(local["confidence"], 0.9)
        self.assertEqual(local["provenance"], "e1")  # original high-confidence source

    def test_stronger_agreeing_evidence_upgrades(self):
        r = SovereignReducerV0()
        r.apply_event(_obs("e1", "robot_a", "mug", "color", "red", confidence=0.5))
        r.apply_event(_obs("e2", "robot_b", "mug", "color", "red", confidence=0.95))

        local = r.state["local"]["mug:color"]
        self.assertEqual(local["confidence"], 0.95)
        self.assertEqual(local["provenance"], "e2")  # newer, stronger source


class TestMalformedEvents(unittest.TestCase):
    """Reducer must not crash on bad input."""

    def test_none_event(self):
        r = SovereignReducerV0()
        r.apply_event(None)  # type: ignore
        self.assertEqual(r.state["metadata"]["event_count"], 0)

    def test_empty_dict(self):
        r = SovereignReducerV0()
        r.apply_event({})
        self.assertEqual(r.state["metadata"]["event_count"], 1)

    def test_missing_subject(self):
        r = SovereignReducerV0()
        r.apply_event({
            "event_id": "bad1",
            "type": "OBSERVATION",
            "actor": "robot_a",
            "payload": {"predicate": "color", "value": "red"},
        })
        # Should not crash; should skip gracefully
        self.assertEqual(r.state["local"], {})

    def test_missing_predicate(self):
        r = SovereignReducerV0()
        r.apply_event({
            "event_id": "bad2",
            "type": "OBSERVATION",
            "actor": "robot_a",
            "payload": {"subject": "mug", "value": "red"},
        })
        self.assertEqual(r.state["local"], {})

    def test_non_numeric_confidence(self):
        r = SovereignReducerV0()
        r.apply_event({
            "event_id": "bad3",
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": "robot_a",
            "payload": {
                "subject": "mug",
                "predicate": "color",
                "value": "red",
                "confidence": "not_a_number",
            },
        })
        local = r.state["local"].get("mug:color")
        self.assertIsNotNone(local)
        # Should fall back to default, not crash
        self.assertEqual(local["confidence"], 0.5)


class TestUnknownEventTypes(unittest.TestCase):
    """Unknown types: preserve in log, ignore in reducer state."""

    def test_unknown_type_no_crash(self):
        r = SovereignReducerV0()
        r.apply_event({
            "event_id": "u1",
            "type": "MOOD_UPDATE",
            "actor": "robot_a",
            "payload": {"mood": "optimistic"},
        })
        self.assertEqual(r.state["metadata"]["event_count"], 1)
        self.assertIn("MOOD_UPDATE", r._ignored_types)
        # Should not affect any namespace
        self.assertEqual(r.state["local"], {})
        self.assertEqual(r.state["canonical"], {})

    def test_multiple_unknown_types(self):
        r = SovereignReducerV0()
        for i, t in enumerate(["ALPHA", "BETA", "GAMMA"]):
            r.apply_event({"event_id": f"u{i}", "type": t, "actor": "x"})
        self.assertEqual(r.state["metadata"]["event_count"], 3)
        self.assertEqual(r._ignored_types, {"ALPHA", "BETA", "GAMMA"})


class TestNamespaceNormalization(unittest.TestCase):

    def test_invalid_namespace_defaults_to_local(self):
        r = SovereignReducerV0()
        r.apply_event(_obs("e1", "robot_a", "mug", "color", "red", ns="invalid_ns"))
        self.assertIn("mug:color", r.state["local"])

    def test_none_namespace_defaults_to_local(self):
        r = SovereignReducerV0()
        event = _obs("e1", "robot_a", "mug", "color", "red")
        event["namespace"] = None
        r.apply_event(event)
        self.assertIn("mug:color", r.state["local"])


class TestReducerEpoch(unittest.TestCase):
    """REDUCER_EPOCH events should be tracked in metadata."""

    def test_epoch_recorded(self):
        r = SovereignReducerV0()
        r.apply_event({
            "event_id": "epoch1",
            "type": "REDUCER_EPOCH",
            "actor": "system",
            "payload": {
                "epoch_id": "epoch_2026_02",
                "reducer_hash": "sha256:abc123",
                "ontology_versions": {"perception": "v1"},
            },
        })
        epoch = r.state["metadata"]["current_epoch"]
        self.assertIsNotNone(epoch)
        self.assertEqual(epoch["epoch_id"], "epoch_2026_02")
        self.assertEqual(epoch["reducer_hash"], "sha256:abc123")


class TestEventOrderSensitivity(unittest.TestCase):
    """Different event orderings may produce different state (this is expected)."""

    def test_order_matters(self):
        events_a = [
            _obs("e1", "robot_a", "mug", "temp", "hot", 0.9),
            _obs("e2", "robot_b", "mug", "temp", "cold", 0.8),
        ]
        events_b = list(reversed(events_a))

        r1 = SovereignReducerV0()
        r1.apply_events(events_a)

        r2 = SovereignReducerV0()
        r2.apply_events(events_b)

        # Both should end up contested (conflicting high-confidence),
        # but internal structure may differ. Key: both reach contested.
        self.assertIn("mug:temp", r1.state["contested"])
        self.assertIn("mug:temp", r2.state["contested"])


class TestEvidenceExport(unittest.TestCase):
    """Evidence audit export."""

    def test_evidence_tracks_all_observations(self):
        r = SovereignReducerV0()
        r.apply_event(_obs("e1", "robot_a", "mug", "color", "red", 0.5))
        r.apply_event(_obs("e2", "robot_b", "mug", "color", "red", 0.7))
        r.apply_event(_obs("e3", "robot_c", "mug", "color", "blue", 0.9))

        evidence = r.export_evidence()
        self.assertIn("mug:color", evidence)
        self.assertEqual(len(evidence["mug:color"]), 3)


if __name__ == "__main__":
    unittest.main()
