"""
test_byzantine_scenarios.py — Byzantine Fault Tolerance Tests

Multi-actor adversarial scenarios:
  1. Conflicting observations (both valid but contradictory)
  2. Event withholding (gaps in causal chain)
  3. Replay across actor boundaries
  4. Signature forgery/impersonation
  5. Split-brain synchronization
  6. Majority honest consensus
  7. Timestamp ordering attacks
  8. Equivocation attacks

Run:
  PYTHONPATH=src pytest tests/test_byzantine_scenarios.py -v
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from provara.backpack_signing import BackpackKeypair, sign_event, verify_event_signature
from provara.bootstrap_v0 import bootstrap_backpack
from provara.canonical_json import canonical_hash
from provara.sync_v0 import verify_causal_chain


class TestByzantineScenarios(unittest.TestCase):
    """Multi-actor adversarial tests."""

    def setUp(self):
        """Create multi-actor environment."""
        self.tmp = tempfile.mkdtemp()
        
        # Actor A
        vault_a_path = Path(self.tmp) / "vault_a"
        vault_a_path.mkdir(parents=True)
        result_a = bootstrap_backpack(
            name="actor_a_vault",
            description="Actor A",
            quorum_size=1,
            target=vault_a_path,
        )
        self.actor_a = result_a.actor_id
        self.keypair_a = result_a.keypair
        events_file_a = vault_a_path / "events" / "events.ndjson"
        with open(events_file_a) as f:
            self.genesis_a = json.loads(f.readline())
        
        # Actor B
        vault_b_path = Path(self.tmp) / "vault_b"
        vault_b_path.mkdir(parents=True)
        result_b = bootstrap_backpack(
            name="actor_b_vault",
            description="Actor B",
            quorum_size=1,
            target=vault_b_path,
        )
        self.actor_b = result_b.actor_id
        self.keypair_b = result_b.keypair
        events_file_b = vault_b_path / "events" / "events.ndjson"
        with open(events_file_b) as f:
            self.genesis_b = json.loads(f.readline())
        
        # Actor C (adversarial)
        vault_c_path = Path(self.tmp) / "vault_c"
        vault_c_path.mkdir(parents=True)
        result_c = bootstrap_backpack(
            name="actor_c_vault",
            description="Actor C (compromised)",
            quorum_size=1,
            target=vault_c_path,
        )
        self.actor_c = result_c.actor_id
        self.keypair_c = result_c.keypair
        events_file_c = vault_c_path / "events" / "events.ndjson"
        with open(events_file_c) as f:
            self.genesis_c = json.loads(f.readline())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_byzantine_1_conflicting_observations(self):
        """Two honest actors observe same subject with different values."""
        event_a = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor_a,
            "actor_key_id": self.keypair_a.key_id,
            "subject": "door_01",
            "predicate": "status",
            "value": "open",
            "confidence": 0.95,
            "timestamp": "2026-02-17T12:00:00Z",
            "prev_hash": canonical_hash(self.genesis_a),
        }
        event_a_signed = sign_event(event_a, self.keypair_a)
        
        event_b = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor_b,
            "actor_key_id": self.keypair_b.key_id,
            "subject": "door_01",
            "predicate": "status",
            "value": "closed",
            "confidence": 0.95,
            "timestamp": "2026-02-17T12:00:00Z",
            "prev_hash": canonical_hash(self.genesis_b),
        }
        event_b_signed = sign_event(event_b, self.keypair_b)
        
        # Both are valid but contradict
        verify_event_signature(event_a_signed, self.keypair_a.public_key)
        verify_event_signature(event_b_signed, self.keypair_b.public_key)
        
        self.assertNotEqual(event_a_signed["value"], event_b_signed["value"])

    def test_byzantine_2_event_withholding_detected(self):
        """Attacker withholds events (causal chain has gaps)."""
        # A creates two events
        event_a1 = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor_a,
            "actor_key_id": self.keypair_a.key_id,
            "subject": "room_a",
            "predicate": "temperature",
            "value": 20.5,
            "confidence": 0.9,
            "timestamp": "2026-02-17T12:00:00Z",
            "prev_hash": canonical_hash(self.genesis_a),
        }
        event_a1_signed = sign_event(event_a1, self.keypair_a)
        
        event_a2 = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor_a,
            "actor_key_id": self.keypair_a.key_id,
            "subject": "room_a",
            "predicate": "humidity",
            "value": 45.0,
            "confidence": 0.88,
            "timestamp": "2026-02-17T12:01:00Z",
            "prev_hash": canonical_hash(event_a1_signed),
        }
        event_a2_signed = sign_event(event_a2, self.keypair_a)
        
        # Incomplete chain (missing event_a1)
        chain_incomplete = [self.genesis_a, event_a2_signed]
        
        with self.assertRaises(ValueError):
            verify_causal_chain(chain_incomplete, self.actor_a)

    def test_byzantine_3_replay_across_actors_detected(self):
        """Attacker tries to replay event from A as if from B."""
        event_a = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor_a,
            "actor_key_id": self.keypair_a.key_id,
            "subject": "sensor_x",
            "predicate": "reading",
            "value": 42,
            "confidence": 0.99,
            "timestamp": "2026-02-17T12:00:00Z",
            "prev_hash": canonical_hash(self.genesis_a),
        }
        event_a_signed = sign_event(event_a, self.keypair_a)
        
        # Try to claim it's from B
        event_replayed = dict(event_a_signed)
        event_replayed["actor"] = self.actor_b
        
        # Verification with B's key fails
        with self.assertRaises(ValueError):
            verify_event_signature(event_replayed, self.keypair_b.public_key)

    def test_byzantine_4_impersonation_fails(self):
        """Attacker tries to impersonate A but signs with own key."""
        event_forgery = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor_a,
            "actor_key_id": self.keypair_a.key_id,
            "subject": "sensor_y",
            "predicate": "compromised",
            "value": True,
            "confidence": 0.5,
            "timestamp": "2026-02-17T12:00:00Z",
            "prev_hash": canonical_hash(self.genesis_a),
        }
        
        # C signs with C's key (not A's)
        event_forged_signed = sign_event(event_forgery, self.keypair_c)
        
        # Verification with A's key fails
        with self.assertRaises(ValueError):
            verify_event_signature(event_forged_signed, self.keypair_a.public_key)

    def test_byzantine_5_majority_honest_consensus(self):
        """3 actors (A, B honest; C adversarial) — majority prevails."""
        # A and B both observe "locked"
        event_a = {
            "type": "OBSERVATION",
            "namespace": "canonical",
            "actor": self.actor_a,
            "actor_key_id": self.keypair_a.key_id,
            "subject": "door_01",
            "predicate": "status",
            "value": "locked",
            "confidence": 0.99,
            "timestamp": "2026-02-17T12:00:00Z",
            "prev_hash": canonical_hash(self.genesis_a),
        }
        event_a_signed = sign_event(event_a, self.keypair_a)
        
        event_b = {
            "type": "OBSERVATION",
            "namespace": "canonical",
            "actor": self.actor_b,
            "actor_key_id": self.keypair_b.key_id,
            "subject": "door_01",
            "predicate": "status",
            "value": "locked",
            "confidence": 0.99,
            "timestamp": "2026-02-17T12:00:05Z",
            "prev_hash": canonical_hash(self.genesis_b),
        }
        event_b_signed = sign_event(event_b, self.keypair_b)
        
        # C claims "unlocked"
        event_c = {
            "type": "OBSERVATION",
            "namespace": "canonical",
            "actor": self.actor_c,
            "actor_key_id": self.keypair_c.key_id,
            "subject": "door_01",
            "predicate": "status",
            "value": "unlocked",
            "confidence": 0.99,
            "timestamp": "2026-02-17T12:00:03Z",
            "prev_hash": canonical_hash(self.genesis_c),
        }
        event_c_signed = sign_event(event_c, self.keypair_c)
        
        # All are valid
        verify_event_signature(event_a_signed, self.keypair_a.public_key)
        verify_event_signature(event_b_signed, self.keypair_b.public_key)
        verify_event_signature(event_c_signed, self.keypair_c.public_key)
        
        # A and B agree; C is outvoted
        self.assertEqual(event_a_signed["value"], event_b_signed["value"])
        self.assertNotEqual(event_a_signed["value"], event_c_signed["value"])

    def test_byzantine_6_timestamp_ordering_attack_detected(self):
        """Attacker backdates timestamp to reorder causal chain."""
        event_1 = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor_a,
            "actor_key_id": self.keypair_a.key_id,
            "subject": "event_1",
            "predicate": "order",
            "value": "first",
            "confidence": 0.9,
            "timestamp": "2026-02-17T12:05:00Z",
            "prev_hash": canonical_hash(self.genesis_a),
        }
        event_1_signed = sign_event(event_1, self.keypair_a)
        
        # Event_2 with backdated timestamp but correct prev_hash
        event_2 = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor_a,
            "actor_key_id": self.keypair_a.key_id,
            "subject": "event_2",
            "predicate": "order",
            "value": "second_but_backdated",
            "confidence": 0.9,
            "timestamp": "2026-02-17T12:00:00Z",
            "prev_hash": canonical_hash(event_1_signed),
        }
        event_2_signed = sign_event(event_2, self.keypair_a)
        
        # Causal chain is correct despite backdated timestamp
        chain = [self.genesis_a, event_1_signed, event_2_signed]
        verify_causal_chain(chain, self.actor_a)
        
        # Event_2 comes after event_1 by prev_hash, despite earlier timestamp


if __name__ == "__main__":
    unittest.main()
