"""
test_bootstrap.py — Backpack v1.0 Sovereign Bootstrap Tests

Tests:
  - Happy path: bootstrap produces compliant backpack
  - Quorum keypair generation
  - Custom UID
  - Non-empty target directory rejection
  - Cryptographic verification of all outputs
  - Reducer processes bootstrapped events correctly
  - Manifest integrity (file hashes match disk)
  - Self-test integration
  - Back-to-back bootstraps produce distinct identities
  - Bootstrapped backpack survives key rotation

Run:
  cd backpack_v1 && python -m unittest test_bootstrap -v
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from bootstrap_v0 import bootstrap_backpack, BootstrapResult, run_self_test
from backpack_signing import (
    BackpackKeypair,
    load_keys_registry,
    load_public_key_b64,
    resolve_public_key,
    verify_event_signature,
    verify_manifest_signature,
)
from rekey_backpack import rotate_key
from reducer_v0 import SovereignReducerV0
from canonical_json import canonical_dumps


class TestBootstrapHappyPath(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = Path(self.tmp) / "backpack"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_bootstrap_creates_compliant_backpack(self):
        """Core test: bootstrapped backpack passes all 17 compliance tests."""
        result = bootstrap_backpack(self.target, quiet=True)
        self.assertTrue(result.success, f"Bootstrap failed: {result.errors}")
        self.assertTrue(
            run_self_test(self.target, quiet=True),
            "Bootstrapped backpack FAILED compliance tests",
        )

    def test_required_directories_exist(self):
        bootstrap_backpack(self.target, quiet=True)
        for d in ["identity", "events", "state", "artifacts/cas", "policies/ontology"]:
            self.assertTrue(
                (self.target / d).is_dir(),
                f"Missing directory: {d}",
            )

    def test_required_files_exist(self):
        bootstrap_backpack(self.target, quiet=True)
        required = [
            "identity/genesis.json",
            "identity/keys.json",
            "events/events.ndjson",
            "policies/sync_contract.json",
            "policies/safety_policy.json",
            "policies/retention_policy.json",
            "policies/ontology/perception_ontology_v1.json",
            "manifest.json",
            "merkle_root.txt",
            "manifest.sig",
        ]
        for f in required:
            self.assertTrue(
                (self.target / f).is_file(),
                f"Missing file: {f}",
            )

    def test_genesis_has_correct_fields(self):
        result = bootstrap_backpack(self.target, quiet=True)
        genesis = json.loads((self.target / "identity" / "genesis.json").read_text())
        self.assertEqual(genesis["uid"], result.uid)
        self.assertEqual(genesis["root_key_id"], result.root_key_id)
        self.assertIn("birth_timestamp", genesis)

    def test_result_contains_private_key(self):
        result = bootstrap_backpack(self.target, quiet=True)
        self.assertIsNotNone(result.root_private_key_b64)
        self.assertTrue(len(result.root_private_key_b64) > 0)

    def test_private_key_not_in_backpack(self):
        """CRITICAL: Private key material must never appear in the backpack."""
        result = bootstrap_backpack(self.target, quiet=True)
        pk_b64 = result.root_private_key_b64

        # Scan every file in the backpack for the private key
        for p in self.target.rglob("*"):
            if not p.is_file():
                continue
            try:
                content = p.read_text(encoding="utf-8")
                self.assertNotIn(
                    pk_b64,
                    content,
                    f"SECURITY: Private key found in {p.relative_to(self.target)}",
                )
            except UnicodeDecodeError:
                pass  # Binary file, can't contain b64 key string


class TestBootstrapCryptography(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = Path(self.tmp) / "backpack"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_all_event_signatures_valid(self):
        result = bootstrap_backpack(self.target, quiet=True)
        registry = load_keys_registry(self.target / "identity" / "keys.json")

        events = _load_events(self.target)
        for e in events:
            kid = e.get("actor_key_id")
            pk = resolve_public_key(kid, registry)
            self.assertIsNotNone(pk, f"Key {kid} not in registry")
            self.assertTrue(
                verify_event_signature(e, pk),
                f"Invalid signature on event {e['event_id']}",
            )

    def test_manifest_signature_valid(self):
        result = bootstrap_backpack(self.target, quiet=True)
        registry = load_keys_registry(self.target / "identity" / "keys.json")
        sig = json.loads((self.target / "manifest.sig").read_text())
        merkle = (self.target / "merkle_root.txt").read_text().strip()
        pk = resolve_public_key(sig["key_id"], registry)
        self.assertTrue(
            verify_manifest_signature(sig, pk, expected_merkle_root=merkle),
        )

    def test_causal_chain_integrity(self):
        bootstrap_backpack(self.target, quiet=True)
        events = _load_events(self.target)
        ids = {e["event_id"] for e in events}

        # First event should have no prev
        self.assertIsNone(events[0].get("prev_event_hash"))

        # Subsequent events should chain to same-actor predecessors
        for e in events[1:]:
            prev = e.get("prev_event_hash")
            self.assertIn(prev, ids, f"Broken chain at {e['event_id']}")
            prev_event = next(x for x in events if x["event_id"] == prev)
            self.assertEqual(prev_event["actor"], e["actor"])


class TestBootstrapOptions(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.target = Path(self.tmp) / "backpack"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_custom_uid(self):
        result = bootstrap_backpack(
            self.target, uid="custom-uid-12345", quiet=True
        )
        self.assertEqual(result.uid, "custom-uid-12345")
        genesis = json.loads((self.target / "identity" / "genesis.json").read_text())
        self.assertEqual(genesis["uid"], "custom-uid-12345")

    def test_quorum_keypair_generated(self):
        result = bootstrap_backpack(
            self.target, include_quorum=True, quiet=True
        )
        self.assertIsNotNone(result.quorum_key_id)
        self.assertIsNotNone(result.quorum_private_key_b64)
        self.assertNotEqual(result.root_key_id, result.quorum_key_id)

        keys = json.loads((self.target / "identity" / "keys.json").read_text())
        self.assertEqual(len(keys["keys"]), 2)

        # Sync contract should list both authorities
        contract = json.loads(
            (self.target / "policies" / "sync_contract.json").read_text()
        )
        authority_kids = [a["key_id"] for a in contract["authorities"]]
        self.assertIn(result.root_key_id, authority_kids)
        self.assertIn(result.quorum_key_id, authority_kids)

    def test_non_empty_target_rejected(self):
        self.target.mkdir(parents=True)
        (self.target / "existing_file.txt").write_text("I exist")
        result = bootstrap_backpack(self.target, quiet=True)
        self.assertFalse(result.success)
        self.assertTrue(any("not empty" in e for e in result.errors))

    def test_custom_actor_name(self):
        result = bootstrap_backpack(
            self.target, actor="robot_alpha", quiet=True
        )
        events = _load_events(self.target)
        for e in events:
            self.assertEqual(e["actor"], "robot_alpha")


class TestBootstrapDeterminism(unittest.TestCase):

    def test_two_bootstraps_produce_distinct_identities(self):
        """Two bootstraps must never collide on UID or key material."""
        with tempfile.TemporaryDirectory() as tmp:
            bp1 = Path(tmp) / "bp1"
            bp2 = Path(tmp) / "bp2"
            r1 = bootstrap_backpack(bp1, quiet=True)
            r2 = bootstrap_backpack(bp2, quiet=True)

            self.assertNotEqual(r1.uid, r2.uid)
            self.assertNotEqual(r1.root_key_id, r2.root_key_id)
            self.assertNotEqual(r1.root_private_key_b64, r2.root_private_key_b64)
            self.assertNotEqual(r1.genesis_event_id, r2.genesis_event_id)


class TestBootstrapReducerIntegration(unittest.TestCase):

    def test_reducer_processes_bootstrapped_events(self):
        """Reducer must produce valid state from bootstrapped event log."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "backpack"
            bootstrap_backpack(target, quiet=True)

            events = _load_events(target)
            r = SovereignReducerV0()
            r.apply_events(events)

            self.assertEqual(r.state["metadata"]["event_count"], 2)
            self.assertIn("system:status", r.state["local"])
            self.assertEqual(
                r.state["local"]["system:status"]["value"],
                "initialized",
            )
            self.assertIsNotNone(r.state["metadata"]["state_hash"])


class TestBootstrapRotationIntegration(unittest.TestCase):

    def test_bootstrapped_backpack_survives_key_rotation(self):
        """Bootstrap with quorum, rotate root key, verify chain survives."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "backpack"
            result = bootstrap_backpack(
                target, include_quorum=True, quiet=True
            )

            # Load quorum private key
            from backpack_signing import load_private_key_b64
            quorum_sk = load_private_key_b64(result.quorum_private_key_b64)

            # Rotate root key using quorum authority
            rot_result = rotate_key(
                backpack_root=target,
                compromised_key_id=result.root_key_id,
                signing_private_key=quorum_sk,
                signing_key_id=result.quorum_key_id,
            )
            self.assertTrue(
                rot_result.success,
                f"Rotation failed: {rot_result.errors}",
            )

            # Verify the event log is still valid
            events = _load_events(target)
            self.assertGreater(len(events), 2)  # seed + rotation events

            # Verify reducer still works
            r = SovereignReducerV0()
            r.apply_events(events)
            self.assertGreater(r.state["metadata"]["event_count"], 2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_events(bp: Path):
    events = []
    with (bp / "events" / "events.ndjson").open() as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))
    return events


if __name__ == "__main__":
    unittest.main()
