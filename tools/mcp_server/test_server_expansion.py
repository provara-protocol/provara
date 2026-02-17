import json
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

# Reuse helpers from test_server.py
sys.path.insert(0, str(Path(__file__).parent))
from test_server import _stdio_request, _stop_proc

class TestMCPServerExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_script = Path(__file__).parent / "server.py"
        cls.psmc_script = Path(__file__).parent.parent / "psmc" / "psmc.py"
        cls.vault_path = Path(__file__).parent / "test_vault_expansion"

    def setUp(self):
        if self.vault_path.exists():
            shutil.rmtree(self.vault_path, ignore_errors=True)
        
        # Init and seed
        subprocess.run([sys.executable, str(self.psmc_script), "--vault", str(self.vault_path), "init"], check=True, capture_output=True)
        subprocess.run([sys.executable, str(self.psmc_script), "--vault", str(self.vault_path), "seed"], check=True, capture_output=True)

    def tearDown(self):
        if self.vault_path.exists():
            shutil.rmtree(self.vault_path, ignore_errors=True)

    def _get_proc(self):
        return subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    def test_snapshot_belief(self):
        proc = self._get_proc()
        resp = _stdio_request(proc, "tools/call", {
            "name": "snapshot_belief",
            "arguments": {"vault_path": str(self.vault_path)}
        }, request_id=1)
        _stop_proc(proc)
        
        self.assertIn("result", resp)
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertIn("metadata", content)
        self.assertIn("state_hash", content["metadata"])

    def test_query_timeline(self):
        proc = self._get_proc()
        resp = _stdio_request(proc, "tools/call", {
            "name": "query_timeline",
            "arguments": {"vault_path": str(self.vault_path), "limit": 2}
        }, request_id=1)
        _stop_proc(proc)
        
        self.assertIn("result", resp)
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertIn("events", content)
        self.assertEqual(len(content["events"]), 2)

    def test_list_conflicts(self):
        proc = self._get_proc()
        resp = _stdio_request(proc, "tools/call", {
            "name": "list_conflicts",
            "arguments": {"vault_path": str(self.vault_path)}
        }, request_id=1)
        _stop_proc(proc)
        
        self.assertIn("result", resp)
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertIn("conflicts", content)
        self.assertIsInstance(content["conflicts"], dict)

    def test_export_digest(self):
        proc = self._get_proc()
        resp = _stdio_request(proc, "tools/call", {
            "name": "export_digest",
            "arguments": {"vault_path": str(self.vault_path), "weeks": 1}
        }, request_id=1)
        _stop_proc(proc)
        
        self.assertIn("result", resp)
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertIn("digest", content)
        self.assertTrue(content["digest"].startswith("# Memory Digest"))

    def test_export_markdown(self):
        proc = self._get_proc()
        resp = _stdio_request(proc, "tools/call", {
            "name": "export_markdown",
            "arguments": {"vault_path": str(self.vault_path)}
        }, request_id=1)
        _stop_proc(proc)
        
        self.assertIn("result", resp)
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertIn("markdown", content)
        self.assertTrue(content["markdown"].startswith("# Sovereign Memory Export"))

if __name__ == "__main__":
    unittest.main()
