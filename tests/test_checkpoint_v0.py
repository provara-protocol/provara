"""
test_checkpoint_v0.py — Checkpoint System Tests
"""

import unittest
import json
import shutil
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from provara.checkpoint_v0 import create_checkpoint, verify_checkpoint, save_checkpoint, load_latest_checkpoint
from provara.reducer_v0 import SovereignReducerV0

class TestCheckpoint(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())
        (self.tmp_dir / "merkle_root.txt").write_text("a" * 64, encoding="utf-8")
        
        self.priv = Ed25519PrivateKey.generate()
        self.pub = self.priv.public_key()
        self.kid = "bp1_test_key"
        
        self.reducer = SovereignReducerV0()
        self.reducer.apply_event({
            "type": "OBSERVATION",
            "event_id": "evt_1",
            "actor": "bot",
            "payload": {"subject": "door", "predicate": "state", "value": "open"}
        })
        self.state = self.reducer.export_state()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_create_and_verify_checkpoint(self):
        cp = create_checkpoint(self.tmp_dir, self.state, self.priv, self.kid)
        self.assertEqual(cp.event_count, 1)
        self.assertEqual(cp.last_event_id, "evt_1")
        
        self.assertTrue(verify_checkpoint(cp.to_dict(), self.pub))

    def test_tampered_checkpoint_fails(self):
        cp = create_checkpoint(self.tmp_dir, self.state, self.priv, self.kid)
        cp_dict = cp.to_dict()
        cp_dict["event_count"] = 2 # Tamper
        
        self.assertFalse(verify_checkpoint(cp_dict, self.pub))

    def test_save_and_load_latest(self):
        cp1 = create_checkpoint(self.tmp_dir, self.state, self.priv, self.kid)
        save_checkpoint(self.tmp_dir, cp1)
        
        # Create a second one with more events
        self.reducer.apply_event({
            "type": "OBSERVATION",
            "event_id": "evt_2",
            "actor": "bot",
            "payload": {"subject": "door", "predicate": "state", "value": "closed"}
        })
        cp2 = create_checkpoint(self.tmp_dir, self.reducer.export_state(), self.priv, self.kid)
        save_checkpoint(self.tmp_dir, cp2)
        
        latest = load_latest_checkpoint(self.tmp_dir)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["event_count"], 2)
        self.assertEqual(latest["last_event_id"], "evt_2")

if __name__ == "__main__":
    unittest.main()
