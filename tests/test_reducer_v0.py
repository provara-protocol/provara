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
from provara.reducer_v0 import SovereignReducerV0
from provara.canonical_json import canonical_dumps, canonical_hash


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


class TestEmptyReplay(unittest.TestCase):
    """Zero events through reducer — empty state must have a valid state hash."""

    def test_all_namespaces_empty(self):
        r = SovereignReducerV0()
        state = r.export_state()
        self.assertEqual(state["canonical"], {})
        self.assertEqual(state["local"], {})
        self.assertEqual(state["contested"], {})
        self.assertEqual(state["archived"], {})

    def test_initial_state_hash_not_none(self):
        """Initial state (no events applied) must have a non-None state hash."""
        r = SovereignReducerV0()
        state_hash = r.state["metadata"]["state_hash"]
        self.assertIsNotNone(state_hash, "Initial state hash must not be None")
        self.assertIsInstance(state_hash, str)
        self.assertEqual(len(state_hash), 64, "State hash must be 64 hex chars")

    def test_initial_event_count_zero(self):
        r = SovereignReducerV0()
        self.assertEqual(r.state["metadata"]["event_count"], 0)

    def test_empty_state_deterministic(self):
        """Two fresh reducers must have identical initial state hashes."""
        r1 = SovereignReducerV0()
        r2 = SovereignReducerV0()
        self.assertEqual(
            r1.state["metadata"]["state_hash"],
            r2.state["metadata"]["state_hash"],
        )

    def test_apply_events_empty_list_unchanged(self):
        """apply_events([]) must not change the state from zero-event baseline."""
        r = SovereignReducerV0()
        initial_hash = r.state["metadata"]["state_hash"]
        r.apply_events([])
        self.assertEqual(r.state["metadata"]["state_hash"], initial_hash)
        self.assertEqual(r.state["metadata"]["event_count"], 0)


class TestNamespaceCollision(unittest.TestCase):
    """Same subject:predicate from two different actors — deterministic resolution."""

    def test_high_confidence_collision_goes_to_contested(self):
        """Two actors with different high-confidence values → contested."""
        r = SovereignReducerV0()
        r.apply_event(_obs("e1", "robot_a", "door", "state", "open", 0.9,
                           ts="2026-02-12T10:00:00Z"))
        r.apply_event(_obs("e2", "robot_b", "door", "state", "closed", 0.9,
                           ts="2026-02-12T10:00:00Z"))
        state = r.export_state()
        self.assertIn("door:state", state["contested"])
        self.assertNotIn("door:state", state["local"])

    def test_collision_state_hash_deterministic(self):
        """Same conflicting events in same order must always produce same state hash."""
        events = [
            _obs("e1", "robot_a", "door", "state", "open", 0.9),
            _obs("e2", "robot_b", "door", "state", "closed", 0.9),
        ]
        hashes = set()
        for _ in range(3):
            r = SovereignReducerV0()
            r.apply_events(events)
            hashes.add(r.state["metadata"]["state_hash"])
        self.assertEqual(len(hashes), 1, "Identical inputs must produce identical state hash")

    def test_both_below_threshold_no_contest(self):
        """Both observations below conflict threshold → local updated, no contest."""
        r = SovereignReducerV0()
        r.apply_event(_obs("e1", "robot_a", "door", "state", "open", 0.3))
        r.apply_event(_obs("e2", "robot_b", "door", "state", "closed", 0.2))
        state = r.export_state()
        # max(0.3, 0.2) = 0.3 < 0.5 default threshold — second observation overwrites first
        self.assertNotIn("door:state", state["contested"])
        self.assertIn("door:state", state["local"])

    def test_contested_has_evidence_for_all_values(self):
        """Contested record must contain evidence for every conflicting value."""
        r = SovereignReducerV0()
        r.apply_event(_obs("e1", "robot_a", "door", "state", "open", 0.9))
        r.apply_event(_obs("e2", "robot_b", "door", "state", "closed", 0.9))
        contested = r.state["contested"]["door:state"]
        self.assertEqual(contested["total_evidence_count"], 2)
        self.assertEqual(len(contested["evidence_by_value"]), 2)

    def test_identical_timestamp_conflict_is_deterministic(self):
        """
        Even with identical timestamps, the winner is determined by log order.
        This ensures that given the same event sequence, the output is identical.
        """
        ts = "2026-02-12T10:00:00Z"
        e1 = _obs("e1", "actor_a", "system", "status", "ok", 0.4, ts=ts)
        e2 = _obs("e2", "actor_b", "system", "status", "error", 0.4, ts=ts)

        # Run 1: e1 then e2
        r1 = SovereignReducerV0()
        r1.apply_events([e1, e2])
        val1 = r1.state["local"]["system:status"]["value"]

        # Run 2: e2 then e1
        r2 = SovereignReducerV0()
        r2.apply_events([e2, e1])
        val2 = r2.state["local"]["system:status"]["value"]

        self.assertEqual(val1, "error", "Last event in sequence must win for low-conf")
        self.assertEqual(val2, "ok", "Last event in sequence must win for low-conf")
        self.assertNotEqual(val1, val2, "Order sensitivity is expected for same-timestamp low-conf")


class TestRetractionEventType(unittest.TestCase):
    """RETRACTION events (PROTOCOL_PROFILE.txt core type) remove active beliefs."""

    def test_retract_local_belief(self):
        r = SovereignReducerV0()
        r.apply_event(_obs("e1", "robot_a", "mug", "color", "red"))
        self.assertIn("mug:color", r.state["local"])

        r.apply_event({
            "event_id": "r1",
            "type": "RETRACTION",
            "actor": "robot_a",
            "payload": {"subject": "mug", "predicate": "color"},
        })
        self.assertNotIn("mug:color", r.state["local"])
        self.assertNotIn("mug:color", r.state["canonical"])
        self.assertNotIn("mug:color", r.state["contested"])

    def test_retract_canonical_belief_archives_it(self):
        """Retracting a canonical belief moves it to archived/ with retracted=True."""
        r = SovereignReducerV0()
        r.apply_event(_attest("a1", "admin", "mug", "color", "red"))
        self.assertIn("mug:color", r.state["canonical"])

        r.apply_event({
            "event_id": "r1",
            "type": "RETRACTION",
            "actor": "admin",
            "payload": {"subject": "mug", "predicate": "color"},
        })
        self.assertNotIn("mug:color", r.state["canonical"])
        archived = r.state["archived"].get("mug:color", [])
        self.assertEqual(len(archived), 1)
        self.assertTrue(archived[0].get("retracted"))
        self.assertEqual(archived[0]["superseded_by"], "r1")

    def test_retract_contested_belief(self):
        r = SovereignReducerV0()
        r.apply_event(_obs("e1", "robot_a", "mug", "color", "red", 0.9))
        r.apply_event(_obs("e2", "robot_b", "mug", "color", "blue", 0.9))
        self.assertIn("mug:color", r.state["contested"])

        r.apply_event({
            "event_id": "r1",
            "type": "RETRACTION",
            "actor": "admin",
            "payload": {"subject": "mug", "predicate": "color"},
        })
        self.assertNotIn("mug:color", r.state["contested"])

    def test_retract_nonexistent_belief_no_crash(self):
        r = SovereignReducerV0()
        r.apply_event({
            "event_id": "r1",
            "type": "RETRACTION",
            "actor": "admin",
            "payload": {"subject": "mug", "predicate": "color"},
        })
        self.assertEqual(r.state["local"], {})
        self.assertEqual(r.state["canonical"], {})

    def test_retraction_missing_subject_skipped(self):
        r = SovereignReducerV0()
        r.apply_event({
            "event_id": "r1",
            "type": "RETRACTION",
            "actor": "admin",
            "payload": {"predicate": "color"},  # missing subject
        })
        # Event still counted, but no state change
        self.assertEqual(r.state["metadata"]["event_count"], 1)
        self.assertEqual(r.state["local"], {})

    def test_retraction_counted_in_event_count(self):
        r = SovereignReducerV0()
        r.apply_event(_obs("e1", "robot_a", "mug", "color", "red"))
        r.apply_event({
            "event_id": "r1",
            "type": "RETRACTION",
            "actor": "robot_a",
            "payload": {"subject": "mug", "predicate": "color"},
        })
        self.assertEqual(r.state["metadata"]["event_count"], 2)

    def test_retraction_state_hash_changes(self):
        """State hash after retraction must differ from hash before."""
        r = SovereignReducerV0()
        r.apply_event(_obs("e1", "robot_a", "mug", "color", "red"))
        hash_before = r.state["metadata"]["state_hash"]

        r.apply_event({
            "event_id": "r1",
            "type": "RETRACTION",
            "actor": "robot_a",
            "payload": {"subject": "mug", "predicate": "color"},
        })
        hash_after = r.state["metadata"]["state_hash"]
        self.assertNotEqual(hash_before, hash_after)


if __name__ == "__main__":
    unittest.main()
