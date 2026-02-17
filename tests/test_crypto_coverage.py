"""
test_crypto_coverage.py — Targeted tests for security-critical code paths
that were missing coverage after the src-layout migration.

Focuses on:
  - backpack_signing: error/rejection branches in verify_* and resolve_*
  - backpack_integrity: path traversal + symlink escape detection
"""

import base64
import tempfile
import unittest
from pathlib import Path

from provara.backpack_signing import (
    BackpackKeypair,
    sign_event,
    verify_event_signature,
    verify_manifest_signature,
    resolve_public_key,
)
from provara.backpack_integrity import (
    canonical_json_str,
    sha256_bytes,
    is_safe_path,
    is_symlink_safe,
)
from provara.canonical_json import canonical_bytes


# ---------------------------------------------------------------------------
# backpack_signing — verify_event_signature error paths
# ---------------------------------------------------------------------------

class TestVerifyEventSignatureErrors(unittest.TestCase):

    def setUp(self):
        self.kp = BackpackKeypair.generate()
        self.event = sign_event(
            {"type": "TEST", "actor": "test", "payload": {}},
            self.kp.private_key,
            self.kp.key_id,
        )

    def test_valid_signature_passes(self):
        self.assertTrue(verify_event_signature(self.event, self.kp.public_key))

    def test_missing_sig_field_returns_false(self):
        evt = {k: v for k, v in self.event.items() if k != "sig"}
        self.assertFalse(verify_event_signature(evt, self.kp.public_key))

    def test_malformed_base64_sig_returns_false(self):
        evt = dict(self.event)
        evt["sig"] = "!!!not-valid-base64!!!"
        self.assertFalse(verify_event_signature(evt, self.kp.public_key))

    def test_tampered_payload_returns_false(self):
        evt = dict(self.event)
        evt["actor"] = "attacker"
        self.assertFalse(verify_event_signature(evt, self.kp.public_key))

    def test_wrong_key_returns_false(self):
        other_kp = BackpackKeypair.generate()
        self.assertFalse(verify_event_signature(self.event, other_kp.public_key))


# ---------------------------------------------------------------------------
# backpack_signing — verify_manifest_signature error paths
# ---------------------------------------------------------------------------

class TestVerifyManifestSignatureErrors(unittest.TestCase):

    def setUp(self):
        self.kp = BackpackKeypair.generate()
        merkle_root = "abc123rootdeadbeef"
        signed_at = "2026-02-17T00:00:00.000000Z"
        signable = {
            "merkle_root": merkle_root,
            "key_id": self.kp.key_id,
            "spec_version": "1.0",
            "signed_at_utc": signed_at,
        }
        sig_bytes = self.kp.private_key.sign(canonical_bytes(signable))
        self.sig_record = {
            **signable,
            "sig": base64.b64encode(sig_bytes).decode("ascii"),
        }

    def test_valid_manifest_sig_passes(self):
        result = verify_manifest_signature(self.sig_record, self.kp.public_key)
        self.assertTrue(result)

    def test_missing_sig_field_returns_false(self):
        record = {k: v for k, v in self.sig_record.items() if k != "sig"}
        self.assertFalse(verify_manifest_signature(record, self.kp.public_key))

    def test_malformed_base64_sig_returns_false(self):
        record = dict(self.sig_record)
        record["sig"] = "!!!not-base64!!!"
        self.assertFalse(verify_manifest_signature(record, self.kp.public_key))

    def test_wrong_key_returns_false(self):
        other_kp = BackpackKeypair.generate()
        self.assertFalse(verify_manifest_signature(self.sig_record, other_kp.public_key))

    def test_merkle_root_mismatch_returns_false(self):
        result = verify_manifest_signature(
            self.sig_record,
            self.kp.public_key,
            expected_merkle_root="wrong_root",
        )
        self.assertFalse(result)

    def test_merkle_root_match_passes(self):
        correct_root = self.sig_record.get("merkle_root")
        result = verify_manifest_signature(
            self.sig_record,
            self.kp.public_key,
            expected_merkle_root=correct_root,
        )
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# backpack_signing — resolve_public_key error paths
# ---------------------------------------------------------------------------

class TestResolvePublicKey(unittest.TestCase):

    def setUp(self):
        self.kp = BackpackKeypair.generate()
        self.registry = {
            self.kp.key_id: {
                "public_key_b64": self.kp.public_key_b64,
                "status": "active",
            }
        }

    def test_valid_key_resolves(self):
        key = resolve_public_key(self.kp.key_id, self.registry)
        self.assertIsNotNone(key)

    def test_unknown_key_id_returns_none(self):
        self.assertIsNone(resolve_public_key("bp1_nonexistent", self.registry))

    def test_revoked_key_returns_none(self):
        registry = {
            self.kp.key_id: {
                "public_key_b64": self.kp.public_key_b64,
                "status": "revoked",
            }
        }
        self.assertIsNone(resolve_public_key(self.kp.key_id, registry))

    def test_missing_pub_b64_returns_none(self):
        registry = {self.kp.key_id: {"status": "active"}}
        self.assertIsNone(resolve_public_key(self.kp.key_id, registry))

    def test_malformed_pub_b64_returns_none(self):
        registry = {
            self.kp.key_id: {
                "public_key_b64": "!!!not-a-key!!!",
                "status": "active",
            }
        }
        self.assertIsNone(resolve_public_key(self.kp.key_id, registry))


# ---------------------------------------------------------------------------
# backpack_integrity — path traversal + symlink safety (security-critical)
# ---------------------------------------------------------------------------

class TestIsPathSafe(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_normal_relative_path_is_safe(self):
        self.assertTrue(is_safe_path(self.root, "events/events.ndjson"))

    def test_dotdot_traversal_is_unsafe(self):
        self.assertFalse(is_safe_path(self.root, "../etc/passwd"))

    def test_dotdot_nested_traversal_is_unsafe(self):
        self.assertFalse(is_safe_path(self.root, "events/../../secret"))

    def test_absolute_path_is_unsafe(self):
        self.assertFalse(is_safe_path(self.root, "/etc/passwd"))

    def test_simple_filename_is_safe(self):
        self.assertTrue(is_safe_path(self.root, "manifest.json"))

    def test_nested_safe_path(self):
        self.assertTrue(is_safe_path(self.root, "events/2026/events.ndjson"))


class TestIsSymlinkSafe(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_regular_file_is_safe(self):
        regular = self.root / "regular.txt"
        regular.write_text("hello")
        self.assertTrue(is_symlink_safe(regular, self.root))

    def test_nonexistent_path_non_symlink_is_safe(self):
        # Non-symlink paths always return True (they simply don't exist)
        path = self.root / "nonexistent.txt"
        self.assertTrue(is_symlink_safe(path, self.root))


# ---------------------------------------------------------------------------
# backpack_integrity — utility functions (previously uncalled)
# ---------------------------------------------------------------------------

class TestIntegrityUtilities(unittest.TestCase):

    def test_canonical_json_str_returns_string(self):
        result = canonical_json_str({"b": 2, "a": 1})
        self.assertIsInstance(result, str)
        # Keys must be sorted per RFC 8785
        self.assertIn('"a"', result)
        self.assertIn('"b"', result)
        self.assertLess(result.index('"a"'), result.index('"b"'))

    def test_sha256_bytes_returns_hex(self):
        result = sha256_bytes(b"hello world")
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 64)  # SHA-256 hex = 64 chars
        # Known value
        import hashlib
        expected = hashlib.sha256(b"hello world").hexdigest()
        self.assertEqual(result, expected)

    def test_sha256_bytes_empty_input(self):
        result = sha256_bytes(b"")
        self.assertEqual(len(result), 64)


if __name__ == "__main__":
    unittest.main()
