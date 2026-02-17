import json
import subprocess
import unittest
import shutil
import tempfile
import sys
from pathlib import Path

# Use the batch wrapper to test real invocation
PROVARA_CMD = str(Path("provara.bat").resolve())

class TestCLIEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.vault = Path(self.tmp) / "cli_test_vault"
        self.keys = Path(self.tmp) / "keys.json"
        self.data_file = Path(self.tmp) / "data.json"
        
        # Write valid JSON data file
        self.data_file.write_text('{"subject": "cli_test", "predicate": "status", "value": 42}', encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        
    def run_provara(self, args):
        # On Windows, run batch file via cmd /c
        if sys.platform == "win32":
            cmd = ["cmd", "/c", PROVARA_CMD] + args
        else:
            cmd = [PROVARA_CMD] + args
            
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding="utf-8"
        )
        return result

    def test_full_lifecycle(self):
        # 1. Init
        res = self.run_provara([
            "init", 
            str(self.vault), 
            "--uid", "test-uid", 
            "--actor", "cli_tester",
            "--private-keys", str(self.keys)
        ])
        if res.returncode != 0:
            print("INIT FAILED stderr:", res.stderr)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Vault created and verified", res.stdout)
        
        # 2. Append
        # Pass data file with @ prefix
        data_arg = f"@{self.data_file}"
        res = self.run_provara([
            "append", 
            str(self.vault), 
            "--type", "OBSERVATION",
            "--actor", "cli_tester",
            "--keyfile", str(self.keys),
            "--data", data_arg
        ])
        if res.returncode != 0:
            print("APPEND FAILED stderr:", res.stderr)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Appended event", res.stdout)
        
        # 3. Replay
        res = self.run_provara(["replay", str(self.vault)])
        self.assertEqual(res.returncode, 0)
        
        state = json.loads(res.stdout)
        # Genesis creates 2 events (GENESIS, OBSERVATION), then we append 1 -> 3 total
        self.assertEqual(state["metadata"]["event_count"], 3) 
        self.assertEqual(state["local"]["cli_test:status"]["value"]["value"], 42)

if __name__ == "__main__":
    unittest.main()
