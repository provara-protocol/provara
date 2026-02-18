import unittest
import sys
from pathlib import Path

# Ensure src is in path for local testing
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import provara

class TestProvaraPackage(unittest.TestCase):
    def test_package_structure(self):
        """Test that the package exposes the expected API."""
        self.assertTrue(hasattr(provara, "SovereignReducer"))
        self.assertTrue(hasattr(provara, "bootstrap_backpack"))
        self.assertTrue(hasattr(provara, "sign_event"))
        self.assertTrue(hasattr(provara, "BackpackKeypair"))
        self.assertTrue(hasattr(provara, "check_safety"))

    def test_basic_flow(self):
        """Test a basic sign-and-reduce flow using the public API."""
        # 1. Identity
        kp = provara.BackpackKeypair.generate()
        
        # 2. Event
        event = {
            "type": "OBSERVATION",
            "actor": "test_actor",
            "payload": {
                "subject": "package",
                "predicate": "status",
                "value": "installed"
            }
        }
        
        # 3. Sign
        # Derive event_id first (protocol requirement)
        eid_hash = provara.canonical_hash(event)
        event["event_id"] = f"evt_{eid_hash[:24]}"
        
        # sign_event(event, private_key, key_id)
        signed = provara.sign_event(event, kp.private_key, kp.key_id)
        
        self.assertIn("sig", signed)
        self.assertIn("event_id", signed)
        
        # 4. Reduce
        reducer = provara.SovereignReducer()
        reducer.apply_events([signed])
        state = reducer.export_state()
        
        self.assertEqual(state["metadata"]["event_count"], 1)
        self.assertIn("package:status", state["local"])

if __name__ == "__main__":
    unittest.main()
