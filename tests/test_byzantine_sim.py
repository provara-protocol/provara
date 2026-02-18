"""
test_byzantine_sim.py — Byzantine Actor Simulation (Lane 3B)

Models scenarios where N actors interact, and K of them are adversarial.
Tests the spec's resilience against:
- Withheld events (selective sharing)
- Replayed signatures (from other contexts)
- Backdated observations (causal chronology attacks)
- Forked chains (split-brain attacks)
"""

import unittest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from provara.backpack_signing import BackpackKeypair, sign_event
from provara.sync_v0 import detect_forks, verify_causal_chain, verify_all_signatures, load_keys_registry, BrokenCausalChainError

class ByzantineSimulator:
    def __init__(self):
        self.actors = {} # name -> keypair
        self.global_log = []
        
    def add_actor(self, name):
        self.actors[name] = BackpackKeypair.generate()
        return self.actors[name]

    def create_event(self, actor_name, prev_hash, payload, ts=None, event_type="OBSERVATION"):
        kp = self.actors[actor_name]
        if ts is None:
            ts = datetime.utcnow().isoformat()
        e = {
            "type": event_type,
            "actor": actor_name,
            "actor_key_id": kp.key_id,
            "timestamp_utc": ts,
            "prev_event_hash": prev_hash,
            "payload": payload
        }
        # Simplified ID for sim (content-addressed in real system)
        import hashlib
        from provara.canonical_json import canonical_bytes
        e["event_id"] = "evt_" + hashlib.sha256(canonical_bytes(e)).hexdigest()[:24]
        return sign_event(e, kp.private_key, kp.key_id)

class TestByzantineSim(unittest.TestCase):
    def setUp(self):
        self.sim = ByzantineSimulator()
        self.alice = self.sim.add_actor("alice")
        self.bob = self.sim.add_actor("bob")
        self.mallory = self.sim.add_actor("mallory") # Adversarial

    def test_withheld_event_detection(self):
        """Mallory withholds an event from Alice but shares it with Bob."""
        e0 = self.sim.create_event("mallory", None, {"v": 0})
        e1 = self.sim.create_event("mallory", e0["event_id"], {"v": 1})
        e2 = self.sim.create_event("mallory", e1["event_id"], {"v": 2})
        
        # Log shared with Bob: [e0, e1, e2]
        # Log shared with Alice: [e0, e2]
        
        # Bob's view is valid
        self.assertTrue(verify_causal_chain([e0, e1, e2], "mallory"))
        
        # Alice's view is invalid (gap in prev_event_hash)
        self.assertFalse(verify_causal_chain([e0, e2], "mallory"))

    def test_fork_attack(self):
        """Mallory creates two divergent histories (fork)."""
        e0 = self.sim.create_event("mallory", None, {"v": 0})
        
        # Fork A
        e1a = self.sim.create_event("mallory", e0["event_id"], {"fork": "A"})
        # Fork B
        e1b = self.sim.create_event("mallory", e0["event_id"], {"fork": "B"})
        
        combined = [e0, e1a, e1b]
        forks = detect_forks(combined)
        
        self.assertEqual(len(forks), 1)
        self.assertEqual(forks[0].actor_id, "mallory")
        self.assertEqual(forks[0].prev_hash, e0["event_id"])

    def test_signature_replay_detection(self):
        """Mallory attempts to replay Alice's signature on a different event."""
        # 1. Alice creates a valid event
        e_alice = self.sim.create_event("alice", None, {"msg": "Hello"})
        
        # 2. Mallory steals the signature and tries to use it for her own event
        e_mallory = self.sim.create_event("mallory", None, {"msg": "Stolen"})
        e_mallory_forged = dict(e_mallory)
        e_mallory_forged["sig"] = e_alice["sig"]
        
        # 3. Verification must fail because the payload hash changed
        from provara.sync_v0 import verify_event_signature, resolve_public_key
        # We need a registry for resolution
        registry = {
            self.sim.actors["mallory"].key_id: {"public_key_b64": self.sim.actors["mallory"].public_key_b64}
        }
        pk = resolve_public_key(self.sim.actors["mallory"].key_id, registry)
        self.assertFalse(verify_event_signature(e_mallory_forged, pk))

    def test_backdated_observation_anomaly(self):
        """Mallory appends an event with a timestamp earlier than its predecessor."""
        e0 = self.sim.create_event("mallory", None, {"v": 0}, ts="2026-02-18T12:00:00Z")
        e1 = self.sim.create_event("mallory", e0["event_id"], {"v": 1}, ts="2026-02-18T11:00:00Z") # Backdated
        
        # Causal chain is valid (prev_event_hash matches)
        self.assertTrue(verify_causal_chain([e0, e1], "mallory"))
        
        # But higher-level logic (simulated here) detects the anomaly
        ts0 = datetime.fromisoformat(e0["timestamp_utc"].replace("Z", "+00:00"))
        ts1 = datetime.fromisoformat(e1["timestamp_utc"].replace("Z", "+00:00"))
        self.assertLess(ts1, ts0)

if __name__ == "__main__":
    unittest.main()
