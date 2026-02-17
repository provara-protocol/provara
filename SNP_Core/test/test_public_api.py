import tempfile
import unittest
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import provara  # noqa: E402


class TestPublicAPI(unittest.TestCase):
    def test_exports_exist(self):
        self.assertTrue(hasattr(provara, "Vault"))
        self.assertTrue(hasattr(provara, "SovereignReducer"))
        self.assertTrue(hasattr(provara, "SovereignReducerV0"))
        self.assertTrue(hasattr(provara, "bootstrap_backpack"))
        self.assertTrue(hasattr(provara, "sync_backpacks"))
        self.assertTrue(hasattr(provara, "BackpackKeypair"))

    def test_vault_create_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault_path = Path(tmp) / "api_vault"
            vault = provara.Vault.create(vault_path, uid="api-test", actor="api_tester", quiet=True)
            self.assertIsInstance(vault, provara.Vault)
            state = vault.replay_state()
            # bootstrap emits GENESIS + seed OBSERVATION => 2 events
            self.assertEqual(state["metadata"]["event_count"], 2)
            self.assertIn("system:status", state["local"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
