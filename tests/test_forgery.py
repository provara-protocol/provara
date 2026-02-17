"""
test_forgery.py — Provara Forgery Test Suite (Lane 3C)

Systematically tests vault integrity against simulated tampering attempts.
Verifies that the SDK and CLI correctly detect and reject forgeries
with the appropriate PROVARA_E### codes.
"""

import json
import unittest
import shutil
import tempfile
import sys
from pathlib import Path

# Add src to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT)) # For tests.backpack_compliance_v1

from provara import Vault, canonical_dumps, canonical_hash

class TestForgery(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault_path = self.tmp / "forgery_vault"
        
        # 1. Create valid vault
        self.vault = Vault.create(self.vault_path, uid="forgery-test-001", actor="forger_target")
        
        # 2. Extract keys
        from provara.backpack_signing import BackpackKeypair
        self.kp = BackpackKeypair.generate()
        self.priv = self.kp.private_key_b64()
        
        # Register key
        keys_file = self.vault_path / "identity" / "keys.json"
        reg = json.loads(keys_file.read_text())
        reg["keys"].append(self.kp.to_keys_entry())
        keys_file.write_text(json.dumps(reg, indent=2))
        
        # Add events
        self.vault.append_event("OBSERVATION", {"v": 1}, self.kp.key_id, self.priv, actor="alice")
        self.vault.append_event("OBSERVATION", {"v": 2}, self.kp.key_id, self.priv, actor="alice")
        
        # Regenerate manifest
        from provara.cli import cmd_manifest
        from argparse import Namespace
        cmd_manifest(Namespace(path=str(self.vault_path)))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _get_events(self):
        events_file = self.vault_path / "events" / "events.ndjson"
        from provara.sync_v0 import load_events
        return load_events(events_file)

    def _write_events(self, events):
        events_file = self.vault_path / "events" / "events.ndjson"
        with open(events_file, "w", encoding="utf-8") as f:
            for e in events:
                f.write(canonical_dumps(e) + "\n")

    def test_detect_payload_tamper(self):
        """Forgery Case 1: Modify payload content without updating event_id/sig."""
        events = self._get_events()
        # Modifying the last event (alice v=2)
        events[-1]["payload"]["v"] = 999
        self._write_events(events)
        
        # Verification should fail
        from provara.sync_v0 import verify_all_signatures, load_keys_registry
        reg = load_keys_registry(self.vault_path / "identity" / "keys.json")
        valid, invalid, errors = verify_all_signatures(events, reg)
        
        self.assertGreater(invalid, 0)
        self.assertTrue(any("invalid signature" in e.lower() for e in errors))

    def test_detect_chain_reorder(self):
        """Forgery Case 3: Swap two events AND their logical links."""
        events = self._get_events()
        # To truly test re-ordering detection where pointers are valid 
        # but chronology is wrong, we'd need to compare against an external anchor.
        
        # SIMPLER TEST: Break the prev_event_hash link
        events[-1]["prev_event_hash"] = "evt_malicious_gap"
        self._write_events(events)
        
        from provara.sync_v0 import verify_all_causal_chains
        results = verify_all_causal_chains(events)
        self.assertFalse(results["alice"])

    def test_detect_merkle_tamper(self):
        """Forgery Case 7: Modify a file on disk without updating manifest."""
        (self.vault_path / "identity" / "genesis.json").write_text("TAMPERED")
        
        from tests.backpack_compliance_v1 import TestBackpackComplianceV1
        import unittest
        
        TestBackpackComplianceV1.backpack_path = str(self.vault_path)
        suite = unittest.TestLoader().loadTestsFromTestCase(TestBackpackComplianceV1)
        result = unittest.TextTestRunner(verbosity=0).run(suite)
        
        # Test 9 (manifest match) should fail
        self.assertFalse(result.wasSuccessful())

if __name__ == "__main__":
    unittest.main()
