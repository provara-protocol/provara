import unittest
import shutil
import tempfile
import json
import argparse
from pathlib import Path
from provara.bootstrap_v0 import bootstrap_backpack
from provara.redaction import redact_event
from provara.sync_v0 import load_events, verify_all_signatures
from provara.backpack_signing import load_keys_registry
from provara.cli import cmd_append, cmd_verify

class TestRedaction(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.vault_path = Path(self.tmp_dir) / "test_vault"
        self.keyfile = Path(self.tmp_dir) / "keys.json"
        
        # 1. Init vault
        result = bootstrap_backpack(
            self.vault_path,
            uid="redaction-test",
            actor="admin",
            quiet=True
        )
        self.root_key_id = result.root_key_id
        
        # Save keys to file
        keys_data = {
            "keys": [
                {
                    "key_id": result.root_key_id,
                    "private_key_b64": result.root_private_key_b64,
                    "algorithm": "Ed25519"
                }
            ]
        }
        self.keyfile.write_text(json.dumps(keys_data))
        
        # 2. Add an event to redact
        ns = argparse.Namespace(
            path=str(self.vault_path),
            type="OBSERVATION",
            data='{"subject": "secret", "predicate": "value", "value": "top-secret-data"}',
            keyfile=str(self.keyfile),
            key_id=self.root_key_id,
            actor="admin",
            confidence=1.0
        )
        cmd_append(ns)
        
        # Find the event_id
        events = load_events(self.vault_path / "events" / "events.ndjson")
        self.target_event = events[-1]
        self.target_id = self.target_event["event_id"]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_redact_success(self):
        # Redact the event
        redact_event(
            vault_path=self.vault_path,
            keyfile_path=self.keyfile,
            target_event_id=self.target_id,
            reason="GDPR_ERASURE",
            authority="Legal Team"
        )
        
        # Verify events
        events = load_events(self.vault_path / "events" / "events.ndjson")
        redacted_evt = next(e for e in events if e["event_id"] == self.target_id)
        redaction_evt = events[-1]
        
        # Check tombstone
        self.assertTrue(redacted_evt["payload"]["redacted"])
        self.assertEqual(redacted_evt["payload"]["redaction_event_id"], redaction_evt["event_id"])
        self.assertIn("original_payload_hash", redacted_evt["payload"])
        
        # Check redaction event
        self.assertEqual(redaction_evt["type"], "com.provara.redaction")
        self.assertEqual(redaction_evt["payload"]["target_event_id"], self.target_id)
        
        # Verify chain and signatures
        registry = load_keys_registry(self.vault_path / "identity" / "keys.json")
        valid, invalid, errors = verify_all_signatures(events, registry)
        self.assertEqual(invalid, 0, f"Verification failed: {errors}")

    def test_provara_verify_passes(self):
        # Redact
        redact_event(
            vault_path=self.vault_path,
            keyfile_path=self.keyfile,
            target_event_id=self.target_id,
            reason="GDPR_ERASURE",
            authority="Legal Team"
        )
        
        # Run provara verify
        ns = argparse.Namespace(
            path=str(self.vault_path),
            verbose=False,
            show_redacted=False
        )
        try:
            cmd_verify(ns)
        except SystemExit as e:
            self.assertEqual(e.code, 0, "provara verify failed with non-zero exit code")

    def test_provara_verify_show_redacted(self):
        # Redact
        redact_event(
            vault_path=self.vault_path,
            keyfile_path=self.keyfile,
            target_event_id=self.target_id,
            reason="GDPR_ERASURE",
            authority="Legal Team"
        )
        
        # Run provara verify --show-redacted
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        ns = argparse.Namespace(
            path=str(self.vault_path),
            verbose=False,
            show_redacted=True
        )
        with redirect_stdout(f):
            try:
                cmd_verify(ns)
            except SystemExit:
                pass
        
        output = f.getvalue()
        self.assertIn("Redacted Events Metadata:", output)
        self.assertIn(f"Target: {self.target_id}", output)
        self.assertIn("Reason: GDPR_ERASURE", output)
        
    def test_redact_nonexistent(self):
        with self.assertRaises(ValueError):
            redact_event(
                self.vault_path,
                self.keyfile,
                "evt_nonexistent",
                "GDPR_ERASURE",
                "Authority"
            )

    def test_redact_idempotent(self):
        # Redact once
        evt1 = redact_event(
            self.vault_path,
            self.keyfile,
            self.target_id,
            "GDPR_ERASURE",
            "Authority"
        )
        
        # Redact again
        evt2 = redact_event(
            self.vault_path,
            self.keyfile,
            self.target_id,
            "GDPR_ERASURE",
            "Authority"
        )
        
        self.assertEqual(evt1["event_id"], evt2["event_id"])
        
        # Should still be only one redaction event in the log (total 4 events: GENESIS, SEED, DATA, REDACT)
        events = load_events(self.vault_path / "events" / "events.ndjson")
        self.assertEqual(len(events), 4)

if __name__ == "__main__":
    unittest.main()
