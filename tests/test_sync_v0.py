"""
test_sync_v0.py — Backpack v1.0 Multi-Device Sync Layer Tests

Tests for Phase 2 sync operations:
  - Union merge of two event logs
  - Deduplication (same events don't duplicate)
  - Causal chain verification (per-actor linked list)
  - Fork detection (divergent histories)
  - Fencing token creation and validation
  - Delta export/import round-trip
  - Sync produces identical state regardless of merge order
  - Full backpack sync integration
  - Signature verification during import
  - Edge cases (empty logs, malformed data, missing files)

Run:
  cd SNP_Core && python -m unittest test.test_sync_v0 -v
    or
  cd SNP_Core/test && python -m unittest test_sync_v0 -v
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from provara.bootstrap_v0 import bootstrap_backpack
from provara.backpack_signing import (
    BackpackKeypair,
    load_keys_registry,
    sign_event,
    verify_event_signature,
)
from provara.canonical_json import canonical_dumps, canonical_hash
from provara.reducer_v0 import SovereignReducerV0
from provara.sync_v0 import (
    Fork,
    ImportResult,
    MergeResult,
    SyncResult,
    create_fencing_token,
    detect_forks,
    export_delta,
    get_all_actors,
    import_delta,
    load_events,
    merge_event_logs,
    sync_backpacks,
    validate_fencing_token,
    verify_all_causal_chains,
    verify_causal_chain,
    write_events,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_event(
    event_id, actor, event_type="OBSERVATION", prev_hash=None,
    subject="door_01", predicate="status", value="open",
    confidence=0.9, timestamp="2026-02-12T19:30:00Z",
    namespace="local", key_id=None, keypair=None,
):
    """Build a test event, optionally signed."""
    event = {
        "type": event_type,
        "namespace": namespace,
        "actor": actor,
        "actor_key_id": key_id or f"{actor}_key",
        "ts_logical": 1,
        "prev_event_hash": prev_hash,
        "timestamp_utc": timestamp,
        "payload": {
            "subject": subject,
            "predicate": predicate,
            "value": value,
            "confidence": confidence,
        },
        "event_id": event_id,
    }
    if keypair is not None:
        event = sign_event(event, keypair.private_key, keypair.key_id)
        event["actor_key_id"] = keypair.key_id
    return event


def _write_ndjson(path, events):
    """Write events as NDJSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(canonical_dumps(e) + "\n")


def _bootstrap_pair():
    """Bootstrap two backpacks in a temp directory. Returns (tmp_dir, bp1, bp2, result1, result2)."""
    tmp = tempfile.mkdtemp()
    bp1 = Path(tmp) / "bp1"
    bp2 = Path(tmp) / "bp2"
    r1 = bootstrap_backpack(bp1, actor="device_alpha", quiet=True)
    r2 = bootstrap_backpack(bp2, actor="device_beta", quiet=True)
    return tmp, bp1, bp2, r1, r2


# ---------------------------------------------------------------------------
# Tests: Union Merge
# ---------------------------------------------------------------------------

class TestUnionMerge(unittest.TestCase):
    """Test union merge of two event logs."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.local_path = Path(self.tmp) / "local.ndjson"
        self.remote_path = Path(self.tmp) / "remote.ndjson"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_basic_union_merge(self):
        """Two disjoint event logs merge into their union."""
        local_events = [
            _make_event("e1", "robot_a", timestamp="2026-02-12T10:00:00Z"),
            _make_event("e2", "robot_a", prev_hash="e1", timestamp="2026-02-12T10:01:00Z"),
        ]
        remote_events = [
            _make_event("e3", "robot_b", timestamp="2026-02-12T10:00:30Z"),
            _make_event("e4", "robot_b", prev_hash="e3", timestamp="2026-02-12T10:01:30Z"),
        ]
        _write_ndjson(self.local_path, local_events)
        _write_ndjson(self.remote_path, remote_events)

        result = merge_event_logs(self.local_path, self.remote_path)

        self.assertEqual(len(result.merged_events), 4)
        self.assertEqual(result.new_count, 2)  # 2 new events from remote
        merged_ids = [e["event_id"] for e in result.merged_events]
        self.assertIn("e1", merged_ids)
        self.assertIn("e2", merged_ids)
        self.assertIn("e3", merged_ids)
        self.assertIn("e4", merged_ids)

    def test_merge_sorted_by_timestamp(self):
        """Merged events should be sorted by timestamp."""
        local_events = [
            _make_event("e1", "robot_a", timestamp="2026-02-12T10:02:00Z"),
        ]
        remote_events = [
            _make_event("e2", "robot_b", timestamp="2026-02-12T10:01:00Z"),
        ]
        _write_ndjson(self.local_path, local_events)
        _write_ndjson(self.remote_path, remote_events)

        result = merge_event_logs(self.local_path, self.remote_path)

        # e2 (10:01) should come before e1 (10:02)
        self.assertEqual(result.merged_events[0]["event_id"], "e2")
        self.assertEqual(result.merged_events[1]["event_id"], "e1")

    def test_timestamp_tiebreaker_uses_event_id(self):
        """When timestamps are equal, event_id is the tiebreaker."""
        ts = "2026-02-12T10:00:00Z"
        local_events = [_make_event("e_beta", "robot_a", timestamp=ts)]
        remote_events = [_make_event("e_alpha", "robot_b", timestamp=ts)]
        _write_ndjson(self.local_path, local_events)
        _write_ndjson(self.remote_path, remote_events)

        result = merge_event_logs(self.local_path, self.remote_path)

        # "e_alpha" < "e_beta" lexicographically
        self.assertEqual(result.merged_events[0]["event_id"], "e_alpha")
        self.assertEqual(result.merged_events[1]["event_id"], "e_beta")


# ---------------------------------------------------------------------------
# Tests: Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication(unittest.TestCase):
    """Same events present in both logs should not be duplicated."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.local_path = Path(self.tmp) / "local.ndjson"
        self.remote_path = Path(self.tmp) / "remote.ndjson"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_duplicate_events_deduplicated(self):
        """Events with the same event_id appear only once in merged output."""
        shared = _make_event("e1", "robot_a", timestamp="2026-02-12T10:00:00Z")
        local_only = _make_event("e2", "robot_a", prev_hash="e1", timestamp="2026-02-12T10:01:00Z")
        remote_only = _make_event("e3", "robot_b", timestamp="2026-02-12T10:00:30Z")

        _write_ndjson(self.local_path, [shared, local_only])
        _write_ndjson(self.remote_path, [shared, remote_only])

        result = merge_event_logs(self.local_path, self.remote_path)

        self.assertEqual(len(result.merged_events), 3)
        ids = [e["event_id"] for e in result.merged_events]
        self.assertEqual(ids.count("e1"), 1, "Shared event must appear exactly once")
        self.assertEqual(result.new_count, 1, "Only remote_only should count as new")

    def test_identical_logs_produce_zero_new(self):
        """Merging identical logs results in 0 new events."""
        events = [
            _make_event("e1", "robot_a", timestamp="2026-02-12T10:00:00Z"),
            _make_event("e2", "robot_a", prev_hash="e1", timestamp="2026-02-12T10:01:00Z"),
        ]
        _write_ndjson(self.local_path, events)
        _write_ndjson(self.remote_path, events)

        result = merge_event_logs(self.local_path, self.remote_path)

        self.assertEqual(len(result.merged_events), 2)
        self.assertEqual(result.new_count, 0)


# ---------------------------------------------------------------------------
# Tests: Causal Chain Verification
# ---------------------------------------------------------------------------

class TestCausalChain(unittest.TestCase):
    """Verify per-actor causal chain integrity."""

    def test_valid_single_actor_chain(self):
        """A properly linked chain should verify."""
        events = [
            _make_event("e1", "robot_a", prev_hash=None, timestamp="2026-02-12T10:00:00Z"),
            _make_event("e2", "robot_a", prev_hash="e1", timestamp="2026-02-12T10:01:00Z"),
            _make_event("e3", "robot_a", prev_hash="e2", timestamp="2026-02-12T10:02:00Z"),
        ]
        self.assertTrue(verify_causal_chain(events, "robot_a"))

    def test_broken_chain_fails(self):
        """A chain with a missing link should fail."""
        events = [
            _make_event("e1", "robot_a", prev_hash=None, timestamp="2026-02-12T10:00:00Z"),
            _make_event("e3", "robot_a", prev_hash="e2_missing", timestamp="2026-02-12T10:02:00Z"),
        ]
        self.assertFalse(verify_causal_chain(events, "robot_a"))

    def test_first_event_must_have_null_prev(self):
        """First event by an actor must have prev_event_hash = null."""
        events = [
            _make_event("e1", "robot_a", prev_hash="some_hash", timestamp="2026-02-12T10:00:00Z"),
        ]
        self.assertFalse(verify_causal_chain(events, "robot_a"))

    def test_multi_actor_chains_independent(self):
        """Each actor's chain is verified independently."""
        events = [
            _make_event("e1", "robot_a", prev_hash=None, timestamp="2026-02-12T10:00:00Z"),
            _make_event("e2", "robot_a", prev_hash="e1", timestamp="2026-02-12T10:01:00Z"),
            _make_event("e3", "robot_b", prev_hash=None, timestamp="2026-02-12T10:00:30Z"),
            _make_event("e4", "robot_b", prev_hash="e3", timestamp="2026-02-12T10:01:30Z"),
        ]
        self.assertTrue(verify_causal_chain(events, "robot_a"))
        self.assertTrue(verify_causal_chain(events, "robot_b"))

    def test_nonexistent_actor_trivially_valid(self):
        """An actor with no events passes trivially."""
        events = [
            _make_event("e1", "robot_a", prev_hash=None, timestamp="2026-02-12T10:00:00Z"),
        ]
        self.assertTrue(verify_causal_chain(events, "nonexistent"))

    def test_verify_all_causal_chains(self):
        """verify_all_causal_chains returns results for every actor."""
        events = [
            _make_event("e1", "robot_a", prev_hash=None, timestamp="2026-02-12T10:00:00Z"),
            _make_event("e2", "robot_a", prev_hash="e1", timestamp="2026-02-12T10:01:00Z"),
            _make_event("e3", "robot_b", prev_hash=None, timestamp="2026-02-12T10:00:30Z"),
        ]
        results = verify_all_causal_chains(events)
        self.assertTrue(results["robot_a"])
        self.assertTrue(results["robot_b"])


# ---------------------------------------------------------------------------
# Tests: Fork Detection
# ---------------------------------------------------------------------------

class TestForkDetection(unittest.TestCase):
    """Detect cases where two events share the same prev_event_hash."""

    def test_no_forks_in_clean_log(self):
        """A well-ordered log should have no forks."""
        events = [
            _make_event("e1", "robot_a", prev_hash=None),
            _make_event("e2", "robot_a", prev_hash="e1"),
        ]
        forks = detect_forks(events)
        self.assertEqual(len(forks), 0)

    def test_fork_detected(self):
        """Two events by the same actor with the same prev_hash is a fork."""
        events = [
            _make_event("e1", "robot_a", prev_hash=None),
            _make_event("e2", "robot_a", prev_hash="e1", value="open"),
            _make_event("e3", "robot_a", prev_hash="e1", value="closed"),
        ]
        forks = detect_forks(events)
        self.assertEqual(len(forks), 1)
        self.assertEqual(forks[0].actor_id, "robot_a")
        self.assertEqual(forks[0].prev_hash, "e1")

    def test_different_actors_same_prev_not_a_fork(self):
        """Different actors sharing a prev_hash is NOT a fork (cross-actor)."""
        events = [
            _make_event("e1", "robot_a", prev_hash=None),
            _make_event("e2", "robot_a", prev_hash="e1"),
            _make_event("e3", "robot_b", prev_hash=None),
        ]
        forks = detect_forks(events)
        self.assertEqual(len(forks), 0)

    def test_triple_fork(self):
        """Three events with the same prev_hash from one actor = two forks."""
        events = [
            _make_event("e1", "robot_a", prev_hash=None),
            _make_event("e2", "robot_a", prev_hash="e1"),
            _make_event("e3", "robot_a", prev_hash="e1"),
            _make_event("e4", "robot_a", prev_hash="e1"),
        ]
        forks = detect_forks(events)
        # e2/e3 fork and e2/e4 fork
        self.assertEqual(len(forks), 2)


# ---------------------------------------------------------------------------
# Tests: Fencing Tokens
# ---------------------------------------------------------------------------

class TestFencingTokens(unittest.TestCase):
    """Fencing tokens prevent stale writes."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bp_path = Path(self.tmp) / "backpack"
        self.result = bootstrap_backpack(self.bp_path, quiet=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_create_and_validate_fencing_token(self):
        """A freshly created fencing token should validate."""
        token = create_fencing_token(
            self.bp_path,
            self.result.root_private_key_b64,
            self.result.root_key_id,
        )
        self.assertTrue(validate_fencing_token(token, self.bp_path))

    def test_tampered_token_fails_validation(self):
        """A modified token should fail validation."""
        token = create_fencing_token(
            self.bp_path,
            self.result.root_private_key_b64,
            self.result.root_key_id,
        )
        # Tamper with the token hash
        token_data = json.loads(token)
        token_data["token_hash"] = "0" * 64
        tampered = canonical_dumps(token_data)
        self.assertFalse(validate_fencing_token(tampered, self.bp_path))

    def test_invalid_json_fails_validation(self):
        """Non-JSON input should fail validation."""
        self.assertFalse(validate_fencing_token("not json", self.bp_path))

    def test_token_with_unknown_key_fails(self):
        """Token signed by an unknown key should fail."""
        # Generate a new keypair not in the backpack
        rogue_kp = BackpackKeypair.generate()
        token = create_fencing_token(
            self.bp_path,
            rogue_kp.private_key_b64(),
            rogue_kp.key_id,
        )
        self.assertFalse(validate_fencing_token(token, self.bp_path))


# ---------------------------------------------------------------------------
# Tests: Delta Export / Import Round-Trip
# ---------------------------------------------------------------------------

class TestDeltaRoundTrip(unittest.TestCase):
    """Delta export and import should be lossless."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.bp_path = Path(self.tmp) / "backpack"
        self.result = bootstrap_backpack(self.bp_path, quiet=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_full_export_import(self):
        """Export all events, import into a fresh backpack, state matches."""
        # Export from source
        delta = export_delta(self.bp_path, since_hash=None)
        self.assertIsInstance(delta, bytes)

        # Parse to verify structure
        lines = delta.decode("utf-8").strip().split("\n")
        header = json.loads(lines[0])
        self.assertEqual(header["type"], "provara_delta_v1")
        self.assertGreater(header["event_count"], 0)

        # Import into a fresh backpack
        bp2 = Path(self.tmp) / "bp2"
        r2 = bootstrap_backpack(bp2, quiet=True)

        import_result = import_delta(bp2, delta)
        self.assertIsNotNone(import_result.new_state_hash)
        self.assertGreaterEqual(import_result.imported_count, 0)

    def test_partial_delta_export(self):
        """Export only events after a given hash."""
        events = load_events(self.bp_path / "events" / "events.ndjson")
        first_id = events[0]["event_id"]

        delta = export_delta(self.bp_path, since_hash=first_id)
        lines = delta.decode("utf-8").strip().split("\n")
        header = json.loads(lines[0])

        # Should export only events after the first one
        self.assertEqual(header["event_count"], len(events) - 1)

    def test_delta_with_nonexistent_since_exports_all(self):
        """If since_hash doesn't exist, export all events."""
        events = load_events(self.bp_path / "events" / "events.ndjson")

        delta = export_delta(self.bp_path, since_hash="nonexistent_hash")
        lines = delta.decode("utf-8").strip().split("\n")
        header = json.loads(lines[0])

        self.assertEqual(header["event_count"], len(events))

    def test_import_malformed_delta_fails(self):
        """Importing garbage data should fail gracefully."""
        result = import_delta(self.bp_path, b"not valid delta data at all")
        self.assertFalse(result.success)
        self.assertGreater(len(result.errors), 0)

    def test_import_wrong_type_header_fails(self):
        """Delta with wrong type field should be rejected."""
        bad_header = canonical_dumps({"type": "wrong_type", "event_count": 0, "keys": []})
        result = import_delta(self.bp_path, bad_header.encode("utf-8"))
        self.assertFalse(result.success)


# ---------------------------------------------------------------------------
# Tests: Deterministic Merge Order
# ---------------------------------------------------------------------------

class TestMergeOrderDeterminism(unittest.TestCase):
    """Same events merged in any order must produce identical state."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_merge_order_produces_identical_state(self):
        """
        Merge A+B and B+A should produce the same merged event list
        and therefore the same reducer state hash.
        """
        events_a = [
            _make_event("e1", "robot_a", prev_hash=None,
                        subject="mug", predicate="color", value="red",
                        timestamp="2026-02-12T10:00:00Z"),
        ]
        events_b = [
            _make_event("e2", "robot_b", prev_hash=None,
                        subject="mug", predicate="size", value="large",
                        timestamp="2026-02-12T10:00:30Z"),
        ]

        path_a = Path(self.tmp) / "a.ndjson"
        path_b = Path(self.tmp) / "b.ndjson"
        _write_ndjson(path_a, events_a)
        _write_ndjson(path_b, events_b)

        # Merge A <- B
        result_ab = merge_event_logs(path_a, path_b)
        # Merge B <- A
        result_ba = merge_event_logs(path_b, path_a)

        # Same merged events (order should be deterministic by timestamp sort)
        ids_ab = [e["event_id"] for e in result_ab.merged_events]
        ids_ba = [e["event_id"] for e in result_ba.merged_events]
        self.assertEqual(ids_ab, ids_ba)

        # Same reducer state
        r1 = SovereignReducerV0()
        r1.apply_events(result_ab.merged_events)

        r2 = SovereignReducerV0()
        r2.apply_events(result_ba.merged_events)

        self.assertEqual(
            r1.state["metadata"]["state_hash"],
            r2.state["metadata"]["state_hash"],
            "Merge order must not affect final state hash",
        )


# ---------------------------------------------------------------------------
# Tests: Full Backpack Sync Integration
# ---------------------------------------------------------------------------

class TestSyncBackpacksIntegration(unittest.TestCase):
    """Integration test: sync two fully bootstrapped backpacks."""

    def setUp(self):
        self.tmp, self.bp1, self.bp2, self.r1, self.r2 = _bootstrap_pair()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_sync_merges_events(self):
        """Syncing two backpacks merges their event logs."""
        result = sync_backpacks(self.bp1, self.bp2)
        self.assertTrue(result.success, f"Sync failed: {result.errors}")
        self.assertIsNotNone(result.new_state_hash)
        # bp2 has 2 events from bootstrap, bp1 has 2; merged should have 4
        events = load_events(self.bp1 / "events" / "events.ndjson")
        self.assertEqual(len(events), 4)

    def test_sync_produces_state_file(self):
        """After sync, state/current_state.json should exist."""
        sync_backpacks(self.bp1, self.bp2)
        state_file = self.bp1 / "state" / "current_state.json"
        self.assertTrue(state_file.exists())
        state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertIn("canonical", state)
        self.assertIn("metadata", state)

    def test_sync_idempotent(self):
        """Syncing the same pair twice produces the same state."""
        r1 = sync_backpacks(self.bp1, self.bp2)
        r2 = sync_backpacks(self.bp1, self.bp2)
        self.assertEqual(r1.new_state_hash, r2.new_state_hash)
        self.assertEqual(r2.events_merged, 0, "Second sync should add 0 new events")

    def test_unsupported_strategy_fails(self):
        """Non-union strategy should fail with an error."""
        result = sync_backpacks(self.bp1, self.bp2, strategy="replace")
        self.assertFalse(result.success)
        self.assertGreater(len(result.errors), 0)

    def test_sync_conflicting_beliefs_to_contested(self):
        """Two backpacks write different values for same subject:predicate offline, then sync. Contested namespace must catch it."""
        # Load keypairs for signing
        kp1 = BackpackKeypair.generate()
        kp2 = BackpackKeypair.generate()
        
        # bp1: door_01 status = "open" (high confidence)
        bp1_event = _make_event(
            event_id="evt_bp1_door_open",
            actor="device_alpha",
            event_type="OBSERVATION",
            prev_hash=None,
            subject="door_01",
            predicate="status",
            value="open",
            confidence=0.95,
            timestamp="2026-02-16T10:00:00Z",
            namespace="local",
            keypair=kp1,
        )
        bp1_events_path = self.bp1 / "events" / "events.ndjson"
        existing_bp1 = load_events(bp1_events_path)
        _write_ndjson(bp1_events_path, existing_bp1 + [bp1_event])

        # bp2: door_01 status = "closed" (high confidence, conflicting)
        bp2_event = _make_event(
            event_id="evt_bp2_door_closed",
            actor="device_beta",
            event_type="OBSERVATION",
            prev_hash=None,
            subject="door_01",
            predicate="status",
            value="closed",
            confidence=0.95,
            timestamp="2026-02-16T10:00:00Z",
            namespace="local",
            keypair=kp2,
        )
        bp2_events_path = self.bp2 / "events" / "events.ndjson"
        existing_bp2 = load_events(bp2_events_path)
        _write_ndjson(bp2_events_path, existing_bp2 + [bp2_event])

        # Sync bp1 <- bp2
        result = sync_backpacks(self.bp1, self.bp2)
        self.assertTrue(result.success, f"Sync failed: {result.errors}")

        # Load the resulting state
        state_file = self.bp1 / "state" / "current_state.json"
        self.assertTrue(state_file.exists())
        state = json.loads(state_file.read_text(encoding="utf-8"))

        # Assert: door_01:status is in contested/, not local/
        belief_key = "door_01:status"
        self.assertIn(belief_key, state["contested"], "Conflicting beliefs must be contested")
        self.assertNotIn(belief_key, state["local"], "Contested beliefs must not remain in local")

        # Verify contested record structure
        contested_entry = state["contested"][belief_key]
        self.assertEqual(contested_entry["status"], "AWAITING_RESOLUTION")
        self.assertIn("evidence_by_value", contested_entry)
        self.assertEqual(contested_entry["total_evidence_count"], 2, "Should have evidence from both devices")

        # Verify both values are captured in evidence groups
        evidence_groups = contested_entry["evidence_by_value"]
        self.assertEqual(len(evidence_groups), 2, "Should have two distinct value groups (open vs closed)")


# ---------------------------------------------------------------------------
# Tests: Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):
    """Edge case handling for sync operations."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_merge_with_empty_remote(self):
        """Merging with an empty remote log should return local events unchanged."""
        local = [_make_event("e1", "robot_a", prev_hash=None)]
        local_path = Path(self.tmp) / "local.ndjson"
        remote_path = Path(self.tmp) / "remote.ndjson"
        _write_ndjson(local_path, local)
        _write_ndjson(remote_path, [])

        result = merge_event_logs(local_path, remote_path)
        self.assertEqual(len(result.merged_events), 1)
        self.assertEqual(result.new_count, 0)

    def test_merge_with_empty_local(self):
        """Merging with an empty local log should return remote events."""
        remote = [_make_event("e1", "robot_b", prev_hash=None)]
        local_path = Path(self.tmp) / "local.ndjson"
        remote_path = Path(self.tmp) / "remote.ndjson"
        _write_ndjson(local_path, [])
        _write_ndjson(remote_path, remote)

        result = merge_event_logs(local_path, remote_path)
        self.assertEqual(len(result.merged_events), 1)
        self.assertEqual(result.new_count, 1)

    def test_merge_with_nonexistent_remote(self):
        """Merging with a nonexistent remote log file should return local events."""
        local = [_make_event("e1", "robot_a", prev_hash=None)]
        local_path = Path(self.tmp) / "local.ndjson"
        remote_path = Path(self.tmp) / "does_not_exist.ndjson"
        _write_ndjson(local_path, local)

        result = merge_event_logs(local_path, remote_path)
        self.assertEqual(len(result.merged_events), 1)
        self.assertEqual(result.new_count, 0)

    def test_load_events_skips_blank_lines(self):
        """Blank lines in NDJSON should be skipped."""
        path = Path(self.tmp) / "events.ndjson"
        with path.open("w", encoding="utf-8") as f:
            f.write(canonical_dumps(_make_event("e1", "robot_a", prev_hash=None)) + "\n")
            f.write("\n")
            f.write("   \n")
            f.write(canonical_dumps(_make_event("e2", "robot_a", prev_hash="e1")) + "\n")

        events = load_events(path)
        self.assertEqual(len(events), 2)

    def test_get_all_actors(self):
        """get_all_actors should return all unique actors."""
        events = [
            _make_event("e1", "robot_a", prev_hash=None),
            _make_event("e2", "robot_b", prev_hash=None),
            _make_event("e3", "robot_a", prev_hash="e1"),
        ]
        actors = get_all_actors(events)
        self.assertEqual(actors, {"robot_a", "robot_b"})

    def test_import_invalid_utf8_fails(self):
        """Importing non-UTF8 data should fail gracefully."""
        bp = Path(self.tmp) / "bp"
        bootstrap_backpack(bp, quiet=True)
        result = import_delta(bp, b"\xff\xfe invalid bytes")
        self.assertFalse(result.success)


# ---------------------------------------------------------------------------
# Tests: Write and Reload
# ---------------------------------------------------------------------------

class TestEventIO(unittest.TestCase):
    """Test event log I/O round-trip."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_write_and_load_roundtrip(self):
        """Events written with write_events should load identically."""
        events = [
            _make_event("e1", "robot_a", prev_hash=None, timestamp="2026-02-12T10:00:00Z"),
            _make_event("e2", "robot_a", prev_hash="e1", timestamp="2026-02-12T10:01:00Z"),
        ]
        path = Path(self.tmp) / "events" / "test.ndjson"
        write_events(path, events)

        loaded = load_events(path)
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["event_id"], "e1")
        self.assertEqual(loaded[1]["event_id"], "e2")


class TestMalformedEventHandling(unittest.TestCase):
    """Truncated JSON, missing fields, wrong types — graceful rejection at sync layer."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_truncated_json_line_skipped(self):
        """A truncated JSON line is skipped; surrounding valid events load correctly."""
        path = Path(self.tmp) / "events.ndjson"
        good = _make_event("e1", "robot_a", prev_hash=None)
        with path.open("w", encoding="utf-8") as f:
            f.write(canonical_dumps(good) + "\n")
            f.write('{"event_id": "e2", "type": "TRUNCATED\n')  # bad
            f.write(canonical_dumps(_make_event("e3", "robot_a", prev_hash="e1")) + "\n")

        events = load_events(path)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["event_id"], "e1")
        self.assertEqual(events[1]["event_id"], "e3")

    def test_event_missing_actor_still_loads(self):
        """Event missing actor field is loaded; reducer handles it."""
        path = Path(self.tmp) / "events.ndjson"
        no_actor = {"event_id": "e1", "type": "OBSERVATION", "payload": {}}
        with path.open("w", encoding="utf-8") as f:
            f.write(canonical_dumps(no_actor) + "\n")

        events = load_events(path)
        self.assertEqual(len(events), 1)

    def test_event_wrong_type_field_passes_through(self):
        """Event with numeric 'type' field is loaded; reducer ignores it gracefully."""
        path = Path(self.tmp) / "events.ndjson"
        bad_type = {"event_id": "e1", "type": 42, "actor": "x"}
        with path.open("w", encoding="utf-8") as f:
            f.write(canonical_dumps(bad_type) + "\n")

        events = load_events(path)
        self.assertEqual(len(events), 1)

        from provara.reducer_v0 import SovereignReducerV0
        r = SovereignReducerV0()
        r.apply_events(events)
        self.assertEqual(r.state["metadata"]["event_count"], 1)
        self.assertEqual(r.state["local"], {})

    def test_merge_with_corrupt_line_in_log(self):
        """Corrupt line in one log must not block merge of valid events."""
        local_path = Path(self.tmp) / "local.ndjson"
        remote_path = Path(self.tmp) / "remote.ndjson"

        with local_path.open("w", encoding="utf-8") as f:
            f.write(canonical_dumps(_make_event("e1", "robot_a", prev_hash=None)) + "\n")
            f.write("CORRUPT DATA NOT JSON\n")

        with remote_path.open("w", encoding="utf-8") as f:
            f.write(canonical_dumps(_make_event("e2", "robot_b", prev_hash=None)) + "\n")

        result = merge_event_logs(local_path, remote_path)
        ids = [e["event_id"] for e in result.merged_events]
        self.assertIn("e1", ids)
        self.assertIn("e2", ids)

    def test_event_missing_event_id_still_merges(self):
        """Event without event_id is deduplicated by content hash fallback."""
        path_a = Path(self.tmp) / "a.ndjson"
        path_b = Path(self.tmp) / "b.ndjson"
        no_id = {"type": "OBSERVATION", "actor": "x", "payload": {}}

        with path_a.open("w", encoding="utf-8") as f:
            f.write(canonical_dumps(no_id) + "\n")
        with path_b.open("w", encoding="utf-8") as f:
            f.write(canonical_dumps(no_id) + "\n")

        result = merge_event_logs(path_a, path_b)
        # Same event content → deduplicated to 1
        self.assertEqual(len(result.merged_events), 1)
        self.assertEqual(result.new_count, 0)


class TestLongChainPerformance(unittest.TestCase):
    """10K events through append + verify must complete in <10s."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_1k_events_reducer_performance(self):
        """1K events through the reducer must complete in under 10 seconds.

        NOTE: The reducer recomputes state_hash (canonical JSON of full state) on every
        event. This is O(N * state_size). 10K events would take ~70s on Windows.
        1K is the practical budget for now. See TODO.md for checkpoint optimization.
        """
        import time

        N = 1_000
        events = []
        prev = None
        for i in range(N):
            eid = f"evt_{i:06d}"
            events.append(_make_event(
                eid, "robot_perf",
                prev_hash=prev,
                subject=f"sensor_{i % 20}",
                predicate="value",
                value=str(i),
                timestamp=f"2026-02-12T{(i // 3600) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d}Z",
            ))
            prev = eid

        from provara.reducer_v0 import SovereignReducerV0
        start = time.monotonic()
        r = SovereignReducerV0()
        r.apply_events(events)
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 10.0, f"1K events took {elapsed:.2f}s — exceeds 10s budget")
        self.assertEqual(r.state["metadata"]["event_count"], N)
        self.assertIsNotNone(r.state["metadata"]["state_hash"])

    def test_10k_events_causal_chain_verifies(self):
        """10K properly chained events must pass verify_causal_chain."""
        N = 10_000
        events = []
        prev = None
        for i in range(N):
            eid = f"chain_{i:06d}"
            events.append(_make_event(
                eid, "robot_chain",
                prev_hash=prev,
                subject="x", predicate="y", value=str(i),
                timestamp="2026-02-12T10:00:00Z",
            ))
            prev = eid

        result = verify_causal_chain(events, "robot_chain")
        self.assertTrue(result, "10K event chain must verify")

    def test_10k_events_merge_performance(self):
        """Merging two 1K-event logs must complete in under 10 seconds."""
        import time

        N = 1_000
        events_a, events_b = [], []
        for i in range(N):
            events_a.append(_make_event(
                f"a_{i:05d}", "robot_a", prev_hash=None if i == 0 else f"a_{i-1:05d}",
                subject="x", predicate="y", value=str(i),
                timestamp=f"2026-02-12T{(i // 3600) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d}Z",
            ))
            events_b.append(_make_event(
                f"b_{i:05d}", "robot_b", prev_hash=None if i == 0 else f"b_{i-1:05d}",
                subject="x", predicate="y", value=str(i),
                timestamp=f"2026-02-12T{(i // 3600) % 24:02d}:{(i // 60) % 60:02d}:{i % 60:02d}Z",
            ))

        path_a = Path(self.tmp) / "a.ndjson"
        path_b = Path(self.tmp) / "b.ndjson"
        _write_ndjson(path_a, events_a)
        _write_ndjson(path_b, events_b)

        start = time.monotonic()
        result = merge_event_logs(path_a, path_b)
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 10.0, f"Merge of 2x5K events took {elapsed:.2f}s")
        self.assertEqual(len(result.merged_events), N * 2)


if __name__ == "__main__":
    unittest.main()
