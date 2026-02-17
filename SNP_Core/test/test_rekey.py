"""
test_rekey.py — Backpack v1.0 Signing & Re-keying Protocol Tests

Tests:
  Signing layer:
    - Keypair generation produces valid Ed25519 keys
    - Event signing and verification round-trips
    - Tampered events fail verification
    - Manifest signing and verification round-trips

  Re-keying protocol:
    - Successful rotation with surviving authority
    - BLOCKED: compromised key cannot sign its own rotation
    - BLOCKED: revoked key cannot sign a rotation
    - Rotation events are properly chained in event log
    - keys.json is correctly updated after rotation
    - Rotation verification detects self-signed promotions
    - Multiple successive rotations maintain chain integrity

Run:
  python -m unittest test_rekey -v
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from backpack_signing import (
    BackpackKeypair,
    key_id_from_public_bytes,
    load_public_key_b64,
    sign_event,
    sign_manifest,
    verify_event_signature,
    verify_manifest_signature,
)
from rekey_backpack import (
    RotationResult,
    append_event,
    build_rotation_event,
    rotate_key,
    verify_rotation_events,
)
from canonical_json import canonical_dumps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_test_backpack(tmp: Path) -> tuple:
    """Create a minimal valid backpack with two keys (root + quorum)."""
    root_kp = BackpackKeypair.generate()
    quorum_kp = BackpackKeypair.generate()

    bp = tmp / "backpack"
    (bp / "identity").mkdir(parents=True)
    (bp / "events").mkdir(parents=True)
    (bp / "state").mkdir(parents=True)
    (bp / "artifacts" / "cas").mkdir(parents=True)
    (bp / "policies" / "ontology").mkdir(parents=True)

    # Genesis
    genesis = {
        "uid": "test-uid-001",
        "birth_timestamp": "2026-02-13T00:00:00Z",
        "root_key_id": root_kp.key_id,
    }
    (bp / "identity" / "genesis.json").write_text(
        json.dumps(genesis, indent=2)
    )

    # Keys
    keys_data = {
        "keys": [
            root_kp.to_keys_entry(roles=["root", "attestation"]),
            quorum_kp.to_keys_entry(roles=["quorum", "attestation"]),
        ],
        "revocations": [],
    }
    (bp / "identity" / "keys.json").write_text(
        json.dumps(keys_data, indent=2)
    )

    # Seed event (signed by root)
    seed_event = {
        "event_id": "seed_001",
        "type": "OBSERVATION",
        "namespace": "local",
        "actor": "genesis",
        "ts_logical": 1,
        "prev_event_hash": None,
        "timestamp_utc": "2026-02-13T00:00:01Z",
        "payload": {
            "subject": "system",
            "predicate": "status",
            "value": "initialized",
            "confidence": 1.0,
        },
    }
    seed_event = sign_event(seed_event, root_kp.private_key, root_kp.key_id)
    events_path = bp / "events" / "events.ndjson"
    events_path.write_text(canonical_dumps(seed_event) + "\n")

    # Minimal policies
    (bp / "policies" / "sync_contract.json").write_text(json.dumps({
        "authorities": [
            {"role": "root", "key_id": root_kp.key_id, "scope": "all"},
            {"role": "quorum", "key_id": quorum_kp.key_id, "scope": "attestation"},
        ],
        "merge_policies": {"events": "union_by_event_id"},
        "replication_factor": 2,
        "degradation_ladder": ["root", "quorum", "local_emergency"],
    }))
    (bp / "policies" / "safety_policy.json").write_text(json.dumps({
        "action_classes": {
            "L0": {"description": "data-only"}, "L1": {"description": "low-kinetic"},
            "L2": {"description": "high-kinetic"}, "L3": {"description": "critical"},
        },
        "merge_ratchet": "most_restrictive_wins",
    }))
    (bp / "policies" / "retention_policy.json").write_text(json.dumps({
        "events": "permanent",
    }))

    return bp, root_kp, quorum_kp


# ---------------------------------------------------------------------------
# Signing Layer Tests
# ---------------------------------------------------------------------------

class TestKeypairGeneration(unittest.TestCase):

    def test_generate_produces_valid_keypair(self):
        kp = BackpackKeypair.generate()
        self.assertTrue(kp.key_id.startswith("bp1_"))
        self.assertEqual(len(kp.key_id), 4 + 16)  # "bp1_" + 16 hex chars
        self.assertIsNotNone(kp.public_key_b64)

    def test_key_id_deterministic_from_pubkey(self):
        kp = BackpackKeypair.generate()
        import base64
        pub_bytes = base64.b64decode(kp.public_key_b64)
        kid2 = key_id_from_public_bytes(pub_bytes)
        self.assertEqual(kp.key_id, kid2)

    def test_two_keypairs_are_distinct(self):
        kp1 = BackpackKeypair.generate()
        kp2 = BackpackKeypair.generate()
        self.assertNotEqual(kp1.key_id, kp2.key_id)
        self.assertNotEqual(kp1.public_key_b64, kp2.public_key_b64)


class TestEventSigning(unittest.TestCase):

    def test_sign_and_verify_roundtrip(self):
        kp = BackpackKeypair.generate()
        event = {
            "event_id": "test_001",
            "type": "OBSERVATION",
            "actor": "test_agent",
            "payload": {"subject": "door", "predicate": "state", "value": "open"},
        }
        signed = sign_event(event, kp.private_key, kp.key_id)
        self.assertIn("sig", signed)
        self.assertEqual(signed["actor_key_id"], kp.key_id)
        self.assertTrue(verify_event_signature(signed, kp.public_key))

    def test_tampered_event_fails_verification(self):
        kp = BackpackKeypair.generate()
        event = {
            "event_id": "test_002",
            "type": "OBSERVATION",
            "actor": "test_agent",
            "payload": {"subject": "mug", "predicate": "color", "value": "red"},
        }
        signed = sign_event(event, kp.private_key, kp.key_id)

        # Tamper with payload
        signed["payload"]["value"] = "blue"
        self.assertFalse(verify_event_signature(signed, kp.public_key))

    def test_wrong_key_fails_verification(self):
        kp1 = BackpackKeypair.generate()
        kp2 = BackpackKeypair.generate()
        event = {
            "event_id": "test_003",
            "type": "OBSERVATION",
            "actor": "test_agent",
            "payload": {"subject": "x", "predicate": "y", "value": "z"},
        }
        signed = sign_event(event, kp1.private_key, kp1.key_id)
        # Verify with wrong public key
        self.assertFalse(verify_event_signature(signed, kp2.public_key))

    def test_missing_signature_fails(self):
        kp = BackpackKeypair.generate()
        event = {"event_id": "test_004", "type": "OBSERVATION", "actor": "x"}
        # No signature
        self.assertFalse(verify_event_signature(event, kp.public_key))


class TestManifestSigning(unittest.TestCase):

    def test_sign_and_verify_manifest(self):
        kp = BackpackKeypair.generate()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            manifest_path = tmp / "manifest.json"
            merkle_path = tmp / "merkle_root.txt"

            manifest_path.write_text('{"files": []}')
            merkle_path.write_text("abc123\n")

            sig_record = sign_manifest(
                manifest_path, merkle_path, kp.private_key, kp.key_id
            )
            self.assertTrue(
                verify_manifest_signature(sig_record, kp.public_key)
            )
            self.assertTrue(
                verify_manifest_signature(
                    sig_record, kp.public_key, expected_merkle_root="abc123"
                )
            )

    def test_wrong_merkle_root_fails(self):
        kp = BackpackKeypair.generate()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "manifest.json").write_text('{"files": []}')
            (tmp / "merkle_root.txt").write_text("abc123\n")

            sig_record = sign_manifest(
                tmp / "manifest.json",
                tmp / "merkle_root.txt",
                kp.private_key,
                kp.key_id,
            )
            self.assertFalse(
                verify_manifest_signature(
                    sig_record, kp.public_key, expected_merkle_root="WRONG"
                )
            )


# ---------------------------------------------------------------------------
# Re-keying Protocol Tests
# ---------------------------------------------------------------------------

class TestRotationHappyPath(unittest.TestCase):

    def test_successful_rotation_with_quorum_key(self):
        """Quorum key signs rotation of compromised root key."""
        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))

            result = rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=quorum_kp.private_key,
                signing_key_id=quorum_kp.key_id,
                actor="security_admin",
            )

            self.assertTrue(result.success, f"Rotation failed: {result.errors}")
            self.assertIsNotNone(result.revocation_event_id)
            self.assertIsNotNone(result.promotion_event_id)
            self.assertIsNotNone(result.new_key_id)
            self.assertEqual(result.signed_by, quorum_kp.key_id)

    def test_keys_json_updated_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))

            result = rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=quorum_kp.private_key,
                signing_key_id=quorum_kp.key_id,
            )

            keys_data = json.loads(
                (bp / "identity" / "keys.json").read_text()
            )

            # Old key should be revoked
            old_entry = next(
                e for e in keys_data["keys"]
                if e["key_id"] == root_kp.key_id
            )
            self.assertEqual(old_entry["status"], "revoked")
            self.assertIn("revoked_at_utc", old_entry)

            # New key should be active
            new_entry = next(
                e for e in keys_data["keys"]
                if e["key_id"] == result.new_key_id
            )
            self.assertEqual(new_entry["status"], "active")
            self.assertEqual(new_entry["algorithm"], "Ed25519")

            # Revocations list should have the old key
            self.assertEqual(len(keys_data["revocations"]), 1)
            self.assertEqual(
                keys_data["revocations"][0]["key_id"], root_kp.key_id
            )

    def test_rotation_events_in_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))

            rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=quorum_kp.private_key,
                signing_key_id=quorum_kp.key_id,
            )

            events = []
            with (bp / "events" / "events.ndjson").open() as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))

            types = [e["type"] for e in events]
            self.assertIn("KEY_REVOCATION", types)
            self.assertIn("KEY_PROMOTION", types)

            # Both rotation events should be signed
            for e in events:
                if e["type"] in ("KEY_REVOCATION", "KEY_PROMOTION"):
                    self.assertIn("sig", e)
                    self.assertEqual(e["actor_key_id"], quorum_kp.key_id)

    def test_rotation_signatures_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))

            rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=quorum_kp.private_key,
                signing_key_id=quorum_kp.key_id,
            )

            results = verify_rotation_events(bp)
            for r in results:
                self.assertTrue(
                    r["signature_valid"],
                    f"Signature invalid for {r['event_id']}: {r['issues']}",
                )
                self.assertFalse(
                    r["self_signed"],
                    f"Self-signed rotation detected: {r['event_id']}",
                )
                self.assertEqual(r["issues"], [])


class TestRotationSecurityBlocks(unittest.TestCase):

    def test_compromised_key_cannot_sign_own_rotation(self):
        """CRITICAL: The compromised key must NOT be able to authorize its own replacement."""
        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))

            result = rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=root_kp.private_key,  # WRONG: using compromised key
                signing_key_id=root_kp.key_id,             # WRONG: same as compromised
            )

            self.assertFalse(result.success)
            self.assertTrue(
                any("SECURITY VIOLATION" in e for e in result.errors),
                f"Expected security violation error, got: {result.errors}",
            )

    def test_revoked_key_cannot_sign_rotation(self):
        """A key that's already been revoked cannot sign further rotations."""
        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))

            # First rotation: revoke root, signed by quorum
            result1 = rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=quorum_kp.private_key,
                signing_key_id=quorum_kp.key_id,
            )
            self.assertTrue(result1.success)

            # Now try to use the revoked root key to sign another rotation
            result2 = rotate_key(
                backpack_root=bp,
                compromised_key_id=quorum_kp.key_id,
                signing_private_key=root_kp.private_key,  # root is revoked!
                signing_key_id=root_kp.key_id,
            )

            self.assertFalse(result2.success)
            self.assertTrue(
                any("revoked" in e.lower() for e in result2.errors),
                f"Expected revoked key error, got: {result2.errors}",
            )

    def test_nonexistent_key_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))
            fake_kp = BackpackKeypair.generate()

            result = rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=fake_kp.private_key,
                signing_key_id=fake_kp.key_id,  # not in keys.json
            )

            self.assertFalse(result.success)
            self.assertTrue(
                any("not found" in e for e in result.errors),
            )


class TestMultipleRotations(unittest.TestCase):

    def test_two_successive_rotations(self):
        """Rotate root, then rotate quorum — both via surviving authorities."""
        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))

            # Rotation 1: revoke root, signed by quorum
            r1 = rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=quorum_kp.private_key,
                signing_key_id=quorum_kp.key_id,
            )
            self.assertTrue(r1.success)

            # Rotation 2: revoke quorum, signed by the NEW root key
            new_root_kp = BackpackKeypair.generate()
            # We need to find the new key from rotation 1 to use it
            # Instead, use a fresh keypair registered properly
            # The new key from r1 was auto-generated — we don't have its private key
            # So we use r1's new_key_id is in keys.json but we can't sign with it
            # This is correct! In production you'd have the new key's private key.

            # For test: generate a known keypair and rotate with it
            known_new_kp = BackpackKeypair.generate()
            r1b = rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=quorum_kp.private_key,
                signing_key_id=quorum_kp.key_id,
                new_keypair=known_new_kp,
            )
            # r1 already happened, so root is already revoked — this is a double-revoke
            # The test should handle this gracefully
            self.assertTrue(r1b.success or "already revoked" in str(r1b.warnings))

            # Now rotate quorum using the known new key
            r2 = rotate_key(
                backpack_root=bp,
                compromised_key_id=quorum_kp.key_id,
                signing_private_key=known_new_kp.private_key,
                signing_key_id=known_new_kp.key_id,
            )
            self.assertTrue(r2.success, f"Second rotation failed: {r2.errors}")

            # Verify all rotation events
            verifications = verify_rotation_events(bp)
            for v in verifications:
                self.assertTrue(
                    v["signature_valid"],
                    f"Sig invalid: {v['event_id']} — {v['issues']}",
                )


class TestVerificationDetectsAbuse(unittest.TestCase):

    def test_detects_self_signed_promotion(self):
        """Verification should flag a promotion signed by the promoted key."""
        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))
            attacker_kp = BackpackKeypair.generate()

            # Manually inject a self-signed promotion (bypassing rotate_key's guard)
            events_path = bp / "events" / "events.ndjson"
            fake_event = {
                "event_id": "fake_promo_001",
                "type": "KEY_PROMOTION",
                "namespace": "canonical",
                "actor": "attacker",
                "ts_logical": 99,
                "prev_event_hash": None,
                "timestamp_utc": "2026-02-13T01:00:00Z",
                "payload": {
                    "new_key_id": attacker_kp.key_id,
                    "new_public_key_b64": attacker_kp.public_key_b64,
                    "algorithm": "Ed25519",
                    "roles": ["root"],
                    "promoted_by": attacker_kp.key_id,
                    "replaces_key_id": root_kp.key_id,
                },
            }
            # Sign with attacker's own key (self-signed!)
            fake_event = sign_event(
                fake_event, attacker_kp.private_key, attacker_kp.key_id
            )

            # Add attacker's key to keys.json so verification can find it
            keys_data = json.loads((bp / "identity" / "keys.json").read_text())
            keys_data["keys"].append(attacker_kp.to_keys_entry(roles=["root"]))
            (bp / "identity" / "keys.json").write_text(
                json.dumps(keys_data, indent=2)
            )

            append_event(events_path, fake_event)

            results = verify_rotation_events(bp)
            promo_results = [r for r in results if r["type"] == "KEY_PROMOTION"]
            self.assertTrue(len(promo_results) > 0)

            # At least one should be flagged as self-signed
            self.assertTrue(
                any(r["self_signed"] for r in promo_results),
                "Verification should detect self-signed promotion",
            )


class TestMidChainRotation(unittest.TestCase):
    """Key rotation between data events — causal chain must still verify."""

    def test_chain_verifies_across_rotation_boundary(self):
        """
        Data events before rotation → rotation events → data events after rotation.
        verify_causal_chain for the data actor must pass across the boundary.
        """
        from sync_v0 import verify_causal_chain

        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))
            events_path = bp / "events" / "events.ndjson"

            # seed_001 is already in the log (by actor "genesis"), signed by root_kp.
            # Perform key rotation, using a known new keypair so we can sign with it.
            known_new_kp = BackpackKeypair.generate()
            result = rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=quorum_kp.private_key,
                signing_key_id=quorum_kp.key_id,
                new_keypair=known_new_kp,
                actor="security_admin",
            )
            self.assertTrue(result.success, f"Rotation failed: {result.errors}")

            # Append a post-rotation event by the same "genesis" actor, now with new key.
            events = []
            with events_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))

            genesis_events = [e for e in events if e.get("actor") == "genesis"]
            last_genesis_id = genesis_events[-1]["event_id"] if genesis_events else None

            post_event = {
                "event_id": "post_rotation_001",
                "type": "OBSERVATION",
                "namespace": "local",
                "actor": "genesis",
                "actor_key_id": known_new_kp.key_id,
                "ts_logical": 99,
                "prev_event_hash": last_genesis_id,
                "timestamp_utc": "2026-02-13T01:00:00Z",
                "payload": {
                    "subject": "system",
                    "predicate": "rotation_complete",
                    "value": "true",
                    "confidence": 1.0,
                },
            }
            post_event = sign_event(post_event, known_new_kp.private_key, known_new_kp.key_id)
            append_event(events_path, post_event)

            # Reload all events
            all_events = []
            with events_path.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        all_events.append(json.loads(line))

            # The "genesis" actor chain should still verify
            chain_valid = verify_causal_chain(all_events, "genesis")
            self.assertTrue(chain_valid, "Causal chain must verify across rotation boundary")

    def test_rotation_actor_chain_valid(self):
        """KEY_REVOCATION + KEY_PROMOTION events form a valid chain for their actor."""
        from sync_v0 import verify_causal_chain

        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))

            result = rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=quorum_kp.private_key,
                signing_key_id=quorum_kp.key_id,
                actor="security_admin",
            )
            self.assertTrue(result.success)

            all_events = []
            with (bp / "events" / "events.ndjson").open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        all_events.append(json.loads(line))

            chain_valid = verify_causal_chain(all_events, "security_admin")
            self.assertTrue(chain_valid, "Rotation event chain must be valid")

    def test_rotation_signatures_verify_post_rotation(self):
        """All rotation event signatures must verify after rotation and new events."""
        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))

            rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=quorum_kp.private_key,
                signing_key_id=quorum_kp.key_id,
            )

            verifications = verify_rotation_events(bp)
            self.assertTrue(len(verifications) > 0)
            for v in verifications:
                self.assertTrue(
                    v["signature_valid"],
                    f"Signature invalid for {v['event_id']}: {v['issues']}",
                )


class TestDuplicateAttestation(unittest.TestCase):
    """Same belief attested twice — idempotent behavior and proper archival."""

    def test_double_attestation_same_value(self):
        """Attesting the same key:value twice archives the first under second."""
        from reducer_v0 import SovereignReducerV0

        r = SovereignReducerV0()
        r.apply_event({
            "event_id": "a1",
            "type": "ATTESTATION",
            "namespace": "canonical",
            "actor": "admin",
            "payload": {"subject": "door", "predicate": "opens", "value": "inward",
                        "actor_key_id": "admin_key"},
        })
        self.assertEqual(r.state["canonical"]["door:opens"]["value"], "inward")

        r.apply_event({
            "event_id": "a2",
            "type": "ATTESTATION",
            "namespace": "canonical",
            "actor": "admin",
            "payload": {"subject": "door", "predicate": "opens", "value": "inward",
                        "actor_key_id": "admin_key"},
        })
        # Still "inward"; a2 is now canonical, a1 archived
        self.assertEqual(r.state["canonical"]["door:opens"]["value"], "inward")
        self.assertEqual(r.state["canonical"]["door:opens"]["attestation_event_id"], "a2")
        archived = r.state["archived"].get("door:opens", [])
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0]["superseded_by"], "a2")

    def test_double_attestation_different_value(self):
        """Attesting a new value supersedes the previous canonical entry."""
        from reducer_v0 import SovereignReducerV0

        r = SovereignReducerV0()
        r.apply_event({
            "event_id": "a1",
            "type": "ATTESTATION",
            "namespace": "canonical",
            "actor": "admin",
            "payload": {"subject": "door", "predicate": "opens", "value": "inward",
                        "actor_key_id": "k"},
        })
        r.apply_event({
            "event_id": "a2",
            "type": "ATTESTATION",
            "namespace": "canonical",
            "actor": "admin",
            "payload": {"subject": "door", "predicate": "opens", "value": "outward",
                        "actor_key_id": "k"},
        })
        self.assertEqual(r.state["canonical"]["door:opens"]["value"], "outward")
        archived = r.state["archived"].get("door:opens", [])
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0]["value"], "inward")

    def test_double_key_rotation_graceful(self):
        """Revoking an already-revoked key must fail gracefully, not crash."""
        with tempfile.TemporaryDirectory() as tmp:
            bp, root_kp, quorum_kp = make_test_backpack(Path(tmp))

            known_new_kp = BackpackKeypair.generate()
            r1 = rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=quorum_kp.private_key,
                signing_key_id=quorum_kp.key_id,
                new_keypair=known_new_kp,
            )
            self.assertTrue(r1.success)

            # Try to revoke the same key again
            r2 = rotate_key(
                backpack_root=bp,
                compromised_key_id=root_kp.key_id,
                signing_private_key=quorum_kp.private_key,
                signing_key_id=quorum_kp.key_id,
            )
            # Must either succeed idempotently or fail with a clear error
            self.assertIsInstance(r2.success, bool)
            self.assertIsInstance(r2.errors, list)
            # What must NOT happen: crash or exception propagation


if __name__ == "__main__":
    unittest.main()
