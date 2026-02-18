"""
test_scitt.py — SCITT Phase 1 Event Types

Tests for:
  - com.ietf.scitt.signed_statement
  - com.ietf.scitt.receipt

Covers:
  - Happy-path event creation and field preservation
  - Optional fields (cose_envelope_b64, receipt_b64)
  - Persistence to events.ndjson
  - Causal chain integrity after SCITT events
  - Signature validity
  - Schema validation errors (missing fields, bad formats)
  - Event type constant correctness
  - Core vault unaffected by SCITT imports
"""

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from provara import Vault
from provara.backpack_signing import BackpackKeypair, verify_event_signature, load_public_key_b64
from provara.scitt import (
    SIGNED_STATEMENT_TYPE,
    RECEIPT_TYPE,
    record_scitt_statement,
    record_scitt_receipt,
)
from provara.sync_v0 import load_events, verify_all_causal_chains, verify_all_signatures, load_keys_registry


class TestScittEventTypes(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault_path = self.tmp / "scitt_vault"
        self.vault = Vault.create(
            self.vault_path, uid="scitt-test-001", actor="scitt_genesis", quiet=True
        )

        # Generate a keypair and write a keyfile for signing
        self.kp = BackpackKeypair.generate()
        self.keyfile = self.tmp / "keys.json"
        self.keyfile.write_text(json.dumps({
            "keys": [{
                "key_id": self.kp.key_id,
                "private_key_b64": self.kp.private_key_b64(),
                "algorithm": "Ed25519",
            }]
        }))

        # Register the public key in the vault's key registry
        keys_reg_path = self.vault_path / "identity" / "keys.json"
        reg = json.loads(keys_reg_path.read_text())
        reg["keys"].append(self.kp.to_keys_entry())
        keys_reg_path.write_text(json.dumps(reg, indent=2))

        # Pre-compute a deterministic statement hash for reuse
        self.stmt_hash = hashlib.sha256(b"example statement content").hexdigest()
        self.issuer = "did:provara:" + self.kp.key_id

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -----------------------------------------------------------------------
    # Signed Statement — happy path
    # -----------------------------------------------------------------------

    def test_signed_statement_appended(self):
        """record_scitt_statement appends an event with the correct type."""
        signed = record_scitt_statement(
            self.vault_path, self.keyfile,
            statement_hash=self.stmt_hash,
            content_type="application/json",
            subject="software:example-pkg:v1.0",
            issuer=self.issuer,
        )
        self.assertEqual(signed["type"], SIGNED_STATEMENT_TYPE)
        self.assertTrue(signed["event_id"].startswith("evt_"))
        self.assertIn("sig", signed)
        self.assertIn("actor_key_id", signed)

    def test_signed_statement_payload_fields(self):
        """All required payload fields are preserved exactly."""
        signed = record_scitt_statement(
            self.vault_path, self.keyfile,
            statement_hash=self.stmt_hash,
            content_type="application/cbor",
            subject="sbom:example-lib",
            issuer=self.issuer,
        )
        p = signed["payload"]
        self.assertEqual(p["statement_hash"], self.stmt_hash)
        self.assertEqual(p["content_type"], "application/cbor")
        self.assertEqual(p["subject"], "sbom:example-lib")
        self.assertEqual(p["issuer"], self.issuer)
        self.assertNotIn("cose_envelope_b64", p)

    def test_signed_statement_optional_cose(self):
        """cose_envelope_b64 is included in payload when provided."""
        fake_cose = "aGVsbG8gd29ybGQ="
        signed = record_scitt_statement(
            self.vault_path, self.keyfile,
            statement_hash=self.stmt_hash,
            content_type="application/json",
            subject="pkg:example",
            issuer=self.issuer,
            cose_envelope_b64=fake_cose,
        )
        self.assertEqual(signed["payload"]["cose_envelope_b64"], fake_cose)

    def test_signed_statement_persisted(self):
        """Event is written to events.ndjson and readable by load_events."""
        record_scitt_statement(
            self.vault_path, self.keyfile,
            statement_hash=self.stmt_hash,
            content_type="application/json",
            subject="pkg:example",
            issuer=self.issuer,
        )
        events = load_events(self.vault_path / "events" / "events.ndjson")
        scitt_events = [e for e in events if e.get("type") == SIGNED_STATEMENT_TYPE]
        self.assertEqual(len(scitt_events), 1)

    def test_signed_statement_signature_verifies(self):
        """Ed25519 signature on the signed_statement event is valid."""
        signed = record_scitt_statement(
            self.vault_path, self.keyfile,
            statement_hash=self.stmt_hash,
            content_type="application/json",
            subject="pkg:example",
            issuer=self.issuer,
        )
        pub = load_public_key_b64(self.kp.public_key_b64)
        self.assertTrue(verify_event_signature(signed, pub))

    # -----------------------------------------------------------------------
    # Receipt — happy path
    # -----------------------------------------------------------------------

    def _make_statement(self):
        return record_scitt_statement(
            self.vault_path, self.keyfile,
            statement_hash=self.stmt_hash,
            content_type="application/json",
            subject="pkg:example",
            issuer=self.issuer,
        )

    def test_receipt_appended(self):
        """record_scitt_receipt appends an event with the correct type."""
        stmt = self._make_statement()
        receipt = record_scitt_receipt(
            self.vault_path, self.keyfile,
            statement_event_id=stmt["event_id"],
            transparency_service="https://transparency.example.com/v1",
            inclusion_proof="leaf_hash:abc123",
        )
        self.assertEqual(receipt["type"], RECEIPT_TYPE)
        self.assertTrue(receipt["event_id"].startswith("evt_"))
        self.assertIn("sig", receipt)

    def test_receipt_references_statement(self):
        """Receipt payload references the correct signed_statement event_id."""
        stmt = self._make_statement()
        receipt = record_scitt_receipt(
            self.vault_path, self.keyfile,
            statement_event_id=stmt["event_id"],
            transparency_service="https://ts.example.com",
            inclusion_proof={"leaf": "abc", "path": ["def", "ghi"]},
        )
        p = receipt["payload"]
        self.assertEqual(p["statement_event_id"], stmt["event_id"])
        self.assertEqual(p["transparency_service"], "https://ts.example.com")
        self.assertEqual(p["inclusion_proof"], {"leaf": "abc", "path": ["def", "ghi"]})
        self.assertNotIn("receipt_b64", p)

    def test_receipt_optional_receipt_b64(self):
        """receipt_b64 is included in payload when provided."""
        stmt = self._make_statement()
        receipt = record_scitt_receipt(
            self.vault_path, self.keyfile,
            statement_event_id=stmt["event_id"],
            transparency_service="https://ts.example.com",
            inclusion_proof="proof:data",
            receipt_b64="cmVjZWlwdA==",
        )
        self.assertEqual(receipt["payload"]["receipt_b64"], "cmVjZWlwdA==")

    def test_receipt_signature_verifies(self):
        """Ed25519 signature on the receipt event is valid."""
        stmt = self._make_statement()
        receipt = record_scitt_receipt(
            self.vault_path, self.keyfile,
            statement_event_id=stmt["event_id"],
            transparency_service="https://ts.example.com",
            inclusion_proof="proof:data",
        )
        pub = load_public_key_b64(self.kp.public_key_b64)
        self.assertTrue(verify_event_signature(receipt, pub))

    def test_receipt_persisted(self):
        """Receipt is written to events.ndjson and readable by load_events."""
        stmt = self._make_statement()
        record_scitt_receipt(
            self.vault_path, self.keyfile,
            statement_event_id=stmt["event_id"],
            transparency_service="https://ts.example.com",
            inclusion_proof="proof:data",
        )
        events = load_events(self.vault_path / "events" / "events.ndjson")
        receipts = [e for e in events if e.get("type") == RECEIPT_TYPE]
        self.assertEqual(len(receipts), 1)

    # -----------------------------------------------------------------------
    # Chain integrity
    # -----------------------------------------------------------------------

    def test_chain_integrity_after_scitt_events(self):
        """Causal chain for scitt_agent remains valid after statement + receipt."""
        stmt = self._make_statement()
        record_scitt_receipt(
            self.vault_path, self.keyfile,
            statement_event_id=stmt["event_id"],
            transparency_service="https://ts.example.com",
            inclusion_proof="proof:data",
        )
        events = load_events(self.vault_path / "events" / "events.ndjson")
        results = verify_all_causal_chains(events)
        self.assertTrue(results.get("scitt_agent", False))

    def test_all_signatures_valid_after_scitt_events(self):
        """All events in the vault have valid signatures after SCITT events."""
        stmt = self._make_statement()
        record_scitt_receipt(
            self.vault_path, self.keyfile,
            statement_event_id=stmt["event_id"],
            transparency_service="https://ts.example.com",
            inclusion_proof="proof:data",
        )
        events = load_events(self.vault_path / "events" / "events.ndjson")
        reg = load_keys_registry(self.vault_path / "identity" / "keys.json")
        valid, invalid, errors = verify_all_signatures(events, reg)
        self.assertEqual(invalid, 0, f"Unexpected invalid signatures: {errors}")

    def test_receipt_prev_hash_links_to_statement(self):
        """Receipt's prev_event_hash correctly links to the statement event."""
        stmt = self._make_statement()
        receipt = record_scitt_receipt(
            self.vault_path, self.keyfile,
            statement_event_id=stmt["event_id"],
            transparency_service="https://ts.example.com",
            inclusion_proof="proof:data",
        )
        self.assertEqual(receipt["prev_event_hash"], stmt["event_id"])

    # -----------------------------------------------------------------------
    # Schema validation errors
    # -----------------------------------------------------------------------

    def test_statement_missing_content_type(self):
        """Empty content_type raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            record_scitt_statement(
                self.vault_path, self.keyfile,
                statement_hash=self.stmt_hash,
                content_type="",
                subject="pkg:example",
                issuer=self.issuer,
            )
        self.assertIn("content_type", str(ctx.exception))

    def test_statement_missing_subject(self):
        """Empty subject raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            record_scitt_statement(
                self.vault_path, self.keyfile,
                statement_hash=self.stmt_hash,
                content_type="application/json",
                subject="",
                issuer=self.issuer,
            )
        self.assertIn("subject", str(ctx.exception))

    def test_statement_bad_hash_format(self):
        """Malformed statement_hash (not 64-char hex) raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            record_scitt_statement(
                self.vault_path, self.keyfile,
                statement_hash="not-a-valid-sha256-hash",
                content_type="application/json",
                subject="pkg:example",
                issuer=self.issuer,
            )
        self.assertIn("statement_hash", str(ctx.exception))

    def test_statement_short_hash_rejected(self):
        """statement_hash shorter than 64 chars raises ValueError."""
        with self.assertRaises(ValueError):
            record_scitt_statement(
                self.vault_path, self.keyfile,
                statement_hash="deadbeef",
                content_type="application/json",
                subject="pkg:example",
                issuer=self.issuer,
            )

    def test_receipt_missing_transparency_service(self):
        """Empty transparency_service raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            record_scitt_receipt(
                self.vault_path, self.keyfile,
                statement_event_id="evt_" + "a" * 24,
                transparency_service="",
                inclusion_proof="proof:data",
            )
        self.assertIn("transparency_service", str(ctx.exception))

    def test_receipt_bad_statement_event_id(self):
        """statement_event_id not starting with 'evt_' raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            record_scitt_receipt(
                self.vault_path, self.keyfile,
                statement_event_id="invalid_id_format",
                transparency_service="https://ts.example.com",
                inclusion_proof="proof:data",
            )
        self.assertIn("statement_event_id", str(ctx.exception))

    def test_receipt_missing_inclusion_proof(self):
        """Empty inclusion_proof raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            record_scitt_receipt(
                self.vault_path, self.keyfile,
                statement_event_id="evt_" + "a" * 24,
                transparency_service="https://ts.example.com",
                inclusion_proof="",
            )
        self.assertIn("inclusion_proof", str(ctx.exception))

    # -----------------------------------------------------------------------
    # Type constants and spec compliance
    # -----------------------------------------------------------------------

    def test_type_constants(self):
        """Event type constants match IETF reverse-domain convention."""
        self.assertEqual(SIGNED_STATEMENT_TYPE, "com.ietf.scitt.signed_statement")
        self.assertEqual(RECEIPT_TYPE, "com.ietf.scitt.receipt")

    def test_event_type_not_uppercased(self):
        """SCITT event types preserve lowercase reverse-domain format."""
        signed = record_scitt_statement(
            self.vault_path, self.keyfile,
            statement_hash=self.stmt_hash,
            content_type="application/json",
            subject="pkg:example",
            issuer=self.issuer,
        )
        # Must NOT be uppercased (unlike generic append_event which calls .upper())
        self.assertEqual(signed["type"], "com.ietf.scitt.signed_statement")
        self.assertNotEqual(signed["type"], signed["type"].upper())

    def test_core_vault_unaffected(self):
        """SCITT events append to the log without disturbing genesis or other events."""
        events_file = self.vault_path / "events" / "events.ndjson"
        before = len(load_events(events_file))

        record_scitt_statement(
            self.vault_path, self.keyfile,
            statement_hash=self.stmt_hash,
            content_type="application/json",
            subject="pkg:example",
            issuer=self.issuer,
        )

        after = len(load_events(events_file))
        self.assertEqual(after, before + 1)

        # Genesis event is a non-SCITT type
        events = load_events(events_file)
        genesis = events[0]
        self.assertNotIn("scitt", genesis.get("type", "").lower())


if __name__ == "__main__":
    unittest.main()
