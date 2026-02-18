import argparse
import io
import json
import subprocess
import unittest
import shutil
import tempfile
import sys
from contextlib import redirect_stdout
from pathlib import Path

from provara.bootstrap_v0 import bootstrap_backpack
from provara.cli import (
    _get_timestamp,
    _load_keys,
    cmd_manifest,
    cmd_replay,
    cmd_append,
    cmd_checkpoint,
    cmd_resume,
    cmd_init,
    cmd_backup,
)

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

# ---------------------------------------------------------------------------
# Direct-call tests — exercise cmd_* functions in-process for coverage
# ---------------------------------------------------------------------------

class TestCLIDirectCoverage(unittest.TestCase):
    """
    Call cmd_* functions directly with argparse.Namespace.
    Subprocess tests above verify end-to-end; these tests hit coverage.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.vault_dir = self.root / "test_vault"
        self.keys_file = self.root / "keys.json"

        result = bootstrap_backpack(
            self.vault_dir,
            uid="cli-coverage-test",
            actor="test_actor",
            include_quorum=False,
            quiet=True,
        )
        self.assertTrue(result.success, f"Bootstrap failed: {result.errors}")
        self.kid = result.root_key_id
        self.keys_file.write_text(
            json.dumps({self.kid: result.root_private_key_b64})
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _ns(self, **kwargs: object) -> argparse.Namespace:
        """Construct a Namespace with sensible defaults, overridable per-test."""
        defaults: dict = {
            "path": str(self.vault_dir),
            "keyfile": str(self.keys_file),
            "verbose": False,
            "key_id": None,
            "actor": "test_actor",
            "confidence": 1.0,
            "type": "OBSERVATION",
            "data": '{"subject": "x", "predicate": "y", "value": 1}',
            "to": str(self.root / "Backups"),
            "keep": 3,
            "uid": "cli-coverage-test",
            "quorum": False,
            "private_keys": None,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    # --- utility ---

    def test_get_timestamp_format(self) -> None:
        ts = _get_timestamp()
        import re
        self.assertRegex(ts, r"^\d{4}-\d{2}-\d{2}_\d{6}$")

    def test_load_keys_valid(self) -> None:
        keys = _load_keys(self.keys_file)
        self.assertIn(self.kid, keys)
        self.assertIsInstance(list(keys.values())[0], str)

    def test_load_keys_missing_file_exits(self) -> None:
        with self.assertRaises(SystemExit):
            _load_keys(self.root / "nonexistent.json")

    # --- cmd_manifest ---

    def test_cmd_manifest_writes_files(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_manifest(self._ns())
        self.assertTrue((self.vault_dir / "manifest.json").exists())
        self.assertTrue((self.vault_dir / "merkle_root.txt").exists())
        self.assertIn("merkle_root", buf.getvalue())

    # --- cmd_replay ---

    def test_cmd_replay_returns_valid_state(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_replay(self._ns())
        state = json.loads(buf.getvalue())
        self.assertIn("metadata", state)
        self.assertGreaterEqual(state["metadata"]["event_count"], 1)

    # --- cmd_append ---

    def test_cmd_append_inline_json(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_append(self._ns(
                type="OBSERVATION",
                data='{"subject": "cli_subj", "predicate": "status", "value": 42}',
            ))
        self.assertIn("Appended event", buf.getvalue())

    def test_cmd_append_from_file(self) -> None:
        data_file = self.root / "event.json"
        data_file.write_text(
            '{"subject": "file_subj", "predicate": "result", "value": "ok"}'
        )
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_append(self._ns(data=f"@{data_file}"))
        self.assertIn("Appended event", buf.getvalue())

    def test_cmd_append_missing_data_file_exits(self) -> None:
        with self.assertRaises(SystemExit):
            cmd_append(self._ns(data="@/no/such/file.json"))

    def test_cmd_append_invalid_json_exits(self) -> None:
        with self.assertRaises(SystemExit):
            cmd_append(self._ns(data="not-valid-{json}"))

    def test_cmd_append_specific_key_id(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_append(self._ns(
                key_id=self.kid,
                data='{"subject": "s", "predicate": "p", "value": 1}',
            ))
        self.assertIn("Appended event", buf.getvalue())

    def test_cmd_append_unknown_key_id_exits(self) -> None:
        with self.assertRaises(SystemExit):
            cmd_append(self._ns(key_id="bp1_doesnotexist"))

    # --- cmd_checkpoint ---

    def test_cmd_checkpoint_creates_file(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_checkpoint(self._ns())
        self.assertIn("Checkpoint saved", buf.getvalue())
        checkpoints = list((self.vault_dir / "checkpoints").glob("*.chk"))
        self.assertGreater(len(checkpoints), 0)

    # --- cmd_resume ---

    def test_cmd_resume_generates_markdown(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_resume(self._ns())
        output = buf.getvalue()
        self.assertIn("Provara Verified Resume", output)
        self.assertIn("Performance", output)

    # --- cmd_init ---

    def test_cmd_init_creates_vault(self) -> None:
        new_vault = self.root / "brand_new_vault"
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_init(self._ns(path=str(new_vault), uid="init-test-uid"))
        self.assertIn("SUCCESS", buf.getvalue())
        self.assertTrue(new_vault.is_dir())
        self.assertTrue((new_vault / "events" / "events.ndjson").exists())

    def test_cmd_init_saves_private_keys_when_requested(self) -> None:
        new_vault = self.root / "vault_with_keys"
        saved_keys = self.root / "saved_keys.json"
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_init(self._ns(
                path=str(new_vault),
                uid="init-keys-test",
                private_keys=str(saved_keys),
            ))
        self.assertTrue(saved_keys.exists())
        keys_data = json.loads(saved_keys.read_text())
        # Verify new structured format
        self.assertIn("keys", keys_data)
        self.assertIsInstance(keys_data["keys"], list)
        self.assertEqual(len(keys_data["keys"]), 1)
        self.assertIn("key_id", keys_data["keys"][0])
        self.assertIn("private_key_b64", keys_data["keys"][0])
        self.assertEqual(keys_data["keys"][0]["algorithm"], "Ed25519")

    # --- cmd_backup ---

    def test_cmd_backup_missing_vault_exits(self) -> None:
        with self.assertRaises(SystemExit):
            cmd_backup(self._ns(path=str(self.root / "no_vault_here")))


if __name__ == "__main__":
    unittest.main()
