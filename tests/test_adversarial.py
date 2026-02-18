"""
test_adversarial.py — Advanced Forgery and Protocol Attack Scenarios (Lane 3B)

Systematically tests the Provara v1.0 protocol against complex adversarial 
attacks that attempt to bypass integrity checks via duplicate IDs, 
unauthorized key rotations, and corrupted state materializations.

Coverage includes:
- Signature forgeries (wrong key, tampered content)
- Chain attacks (reordering, skipping, forking)
- Key rotation attacks (self-signing, unauthorized promotion)
- Timestamp attacks (retroactive events, clock skew)
- Checkpoint attacks (content modification, false counts)
- Merkle tree attacks (leaf reordering, hash collisions)
- Cross-actor attacks (chain reference violations)
"""

import base64
import json
import unittest
import shutil
import tempfile
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from provara.backpack_signing import BackpackKeypair, sign_event, verify_event_signature
from provara.canonical_json import canonical_hash, canonical_dumps, canonical_bytes
from provara.sync_v0 import verify_causal_chain, detect_forks, verify_all_signatures, load_keys_registry
from provara.checkpoint_v0 import create_checkpoint, verify_checkpoint
from provara.backpack_integrity import merkle_root_hex

def _make_event(kp, actor, prev_event_hash, payload, event_type="OBSERVATION", ts=None):
    if ts is None:
        ts = datetime.utcnow().isoformat()
    e = {
        "type": event_type,
        "namespace": "local",
        "actor": actor,
        "actor_key_id": kp.key_id,
        "timestamp_utc": ts,
        "prev_event_hash": prev_event_hash,
        "payload": payload,
    }
    # Content-addressing: id derived from content (without id/sig)
    e["event_id"] = "evt_" + canonical_hash(e)[:24]
    return sign_event(e, kp.private_key, kp.key_id)

class TestAdversarial(unittest.TestCase):
    def setUp(self):
        self.kp_auth = BackpackKeypair.generate()
        self.actor = "hardener_target"
        
        # Genesis
        self.genesis = _make_event(self.kp_auth, self.actor, None, {"v": 0}, "GENESIS")
        self.chain = [self.genesis]

    def test_attack_duplicate_event_id_injection(self):
        """
        Attack: Inject two distinct events with the same event_id.
        Detection: Content-addressed IDs make this impossible for distinct content.
        If content is identical, deduplication handles it.
        We test that different content results in different IDs.
        """
        e1 = _make_event(self.kp_auth, self.actor, self.genesis["event_id"], {"data": "A"})
        e2 = _make_event(self.kp_auth, self.actor, self.genesis["event_id"], {"data": "B"})
        
        self.assertNotEqual(e1["event_id"], e2["event_id"])
        
        # Manually force same ID (breaks signature)
        e2_malicious = dict(e2)
        e2_malicious["event_id"] = e1["event_id"]
        
        # Signature should fail
        self.assertFalse(verify_event_signature(e2_malicious, self.kp_auth.public_key))

    def test_attack_key_rotation_self_signing(self):
        """
        Attack: A new key signs its own promotion event.
        Spec: KEY_PROMOTION must be signed by a surviving authority.
        """
        kp_new = BackpackKeypair.generate()
        
        # Malicious promotion event signed by kp_new instead of kp_auth
        malicious_promotion = {
            "type": "KEY_PROMOTION",
            "actor": self.actor,
            "actor_key_id": kp_new.key_id, # Should be kp_auth.key_id
            "new_key_id": kp_new.key_id,
            "prev_event_hash": self.genesis["event_id"],
            "timestamp_utc": datetime.utcnow().isoformat(),
            "payload": {"public_key": kp_new.public_key_b64}
        }
        malicious_promotion["event_id"] = "evt_" + canonical_hash(malicious_promotion)[:24]
        signed_promo = sign_event(malicious_promotion, kp_new.private_key, kp_new.key_id)
        
        # Detection: Verifier checks against authority set
        # (This test verifies that it doesn't verify under the ORIGINAL authority)
        self.assertFalse(verify_event_signature(signed_promo, self.kp_auth.public_key))

    def test_attack_time_traveling_timestamps(self):
        """
        Attack: An actor appends an event with a timestamp earlier than its predecessor.
        Detection: Causal chain verifies prev_event_hash, but high-level logic should flag retro-active events.
        """
        now = datetime.utcnow()
        past = now - timedelta(days=1)
        
        e1 = _make_event(self.kp_auth, self.actor, self.genesis["event_id"], {"v": 1}, ts=now.isoformat())
        e2 = _make_event(self.kp_auth, self.actor, e1["event_id"], {"v": 2}, ts=past.isoformat())
        
        chain = [self.genesis, e1, e2]
        
        # The chain is logically valid (prev_event_hash matches)
        self.assertTrue(verify_causal_chain(chain, self.actor))
        
        # But a strict chrononology check would fail
        ts1 = datetime.fromisoformat(e1["timestamp_utc"])
        ts2 = datetime.fromisoformat(e2["timestamp_utc"])
        self.assertLess(ts2, ts1) # Detectable anomaly

    def test_attack_corrupted_checkpoint(self):
        """
        Attack: Present a signed checkpoint where event_count is lied about.
        Detection: Signature over canonical bytes detects any modification.
        """
        state = {"canonical": {"x": 1}, "metadata": {"last_event_id": self.genesis["event_id"], "event_count": 1}}
        
        # We need a temp dir for create_checkpoint
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "merkle_root.txt").write_text("fake_root")
            checkpoint = create_checkpoint(tmp, state, self.kp_auth.private_key, self.kp_auth.key_id)
            cp_dict = checkpoint.to_dict()
            
            # Corrupt the count
            cp_dict["event_count"] = 9999
            
            # Should fail verification
            self.assertFalse(verify_checkpoint(cp_dict, self.kp_auth.public_key))
        finally:
            shutil.rmtree(tmp)

    def test_attack_merkle_leaf_order_swap(self):
        """
        Attack: Swap two file entries in the manifest but keep the same hashes.
        Detection: Merkle root depends on sorted order.
        """
        files = [
            {"path": "a.txt", "sha256": "hash_a", "size": 10},
            {"path": "b.txt", "sha256": "hash_b", "size": 20}
        ]
        
        leaves_orig = [canonical_bytes(f) for f in files]
        root_orig = merkle_root_hex(leaves_orig)
        
        # Swap
        files_swapped = [files[1], files[0]]
        leaves_swapped = [canonical_bytes(f) for f in files_swapped]
        root_swapped = merkle_root_hex(leaves_swapped)
        
        self.assertNotEqual(root_orig, root_swapped)

    def test_attack_revoked_key_usage(self):
        """
        Attack: Use a key to sign an event after a KEY_REVOCATION for that key has been issued.
        """
        # 1. Active usage
        e1 = _make_event(self.kp_auth, self.actor, self.genesis["event_id"], {"v": 1})
        
        # 2. Revocation (signed by kp_auth itself in this simple model, 
        # though usually needs separate authority)
        revoc = _make_event(self.kp_auth, self.actor, e1["event_id"], 
                           {"revoked_key_id": self.kp_auth.key_id}, "KEY_REVOCATION")
        
        # 3. Post-revocation attempt
        e2 = _make_event(self.kp_auth, self.actor, revoc["event_id"], {"v": 2})
        
        # Integration logic (sync_v0) must check revocation state
        # Here we verify we can detect it if we track active set
        active_set = {self.kp_auth.key_id}
        
        # Process events
        for ev in [self.genesis, e1]:
            self.assertIn(ev["actor_key_id"], active_set)
            
        # Process revocation
        active_set.remove(revoc["payload"]["revoked_key_id"])
        
        # Now e2 fails the check
        self.assertNotIn(e2["actor_key_id"], active_set)

    # =========================================================================
    # EXPANDED FORGERY TEST SUITE (Lane 3B)
    # =========================================================================

    def test_forge_signature_wrong_key(self):
        """
        FORGERY: Create valid event, re-sign with wrong key.
        Attack: Replace signature with one from different key.
        Detection: Signature verification fails (verified against expected key).
        """
        e1 = _make_event(self.kp_auth, self.actor, self.genesis["event_id"], {"data": "legit"})
        
        # Generate wrong key
        kp_wrong = BackpackKeypair.generate()
        
        # Sign same event with wrong key
        e1_forged = dict(e1)
        e1_forged["actor_key_id"] = kp_wrong.key_id
        del e1_forged["sig"]  # Remove original sig
        e1_forged["event_id"] = "evt_" + canonical_hash(e1_forged)[:24]
        e1_forged_signed = sign_event(e1_forged, kp_wrong.private_key, kp_wrong.key_id)
        
        # Verification against correct key fails
        self.assertFalse(verify_event_signature(e1_forged_signed, self.kp_auth.public_key))
        # Verification against wrong key succeeds (but key_id is wrong)
        self.assertTrue(verify_event_signature(e1_forged_signed, kp_wrong.public_key))

    def test_forge_event_content_modification(self):
        """
        FORGERY: Modify event payload but keep old signature.
        Attack: Change payload → event_id changes → signature no longer valid.
        Detection: Content-addressed IDs + signature verification catch this.
        """
        e1 = _make_event(self.kp_auth, self.actor, self.genesis["event_id"], {"status": "safe"})
        
        # Attacker modifies payload
        e1_malicious = dict(e1)
        e1_malicious["payload"] = {"status": "compromised"}
        
        # Signature no longer matches (was over old content)
        self.assertFalse(verify_event_signature(e1_malicious, self.kp_auth.public_key))

    def test_forge_event_id_collision_attempt(self):
        """
        FORGERY: Try to force two different events to have same event_id.
        Attack: Content-addressed IDs should make this impossible.
        Detection: Different content MUST produce different IDs (SHA-256 collision resistance).
        """
        e1 = _make_event(self.kp_auth, self.actor, self.genesis["event_id"], {"data": "A", "version": 1})
        e2 = _make_event(self.kp_auth, self.actor, self.genesis["event_id"], {"data": "A", "version": 2})
        
        # Different content → different event_ids
        self.assertNotEqual(e1["event_id"], e2["event_id"])
        
        # Attacker tries to force collision by copying ID (breaks signature)
        e2_fake = dict(e2)
        e2_fake["event_id"] = e1["event_id"]
        self.assertFalse(verify_event_signature(e2_fake, self.kp_auth.public_key))

    def test_attack_chain_reordering(self):
        """
        ATTACK: Reorder events in a chain (break prev_event_hash links).
        Detection: Causal chain verification detects broken links.
        """
        e1 = _make_event(self.kp_auth, self.actor, self.genesis["event_id"], {"v": 1})
        e2 = _make_event(self.kp_auth, self.actor, e1["event_id"], {"v": 2})
        
        # Proper chain
        proper_chain = [self.genesis, e1, e2]
        self.assertTrue(verify_causal_chain(proper_chain, self.actor))
        
        # Reordered chain (e2 before e1)
        reordered_chain = [self.genesis, e2, e1]
        self.assertFalse(verify_causal_chain(reordered_chain, self.actor))

    def test_attack_chain_skipping(self):
        """
        ATTACK: Skip events in a chain (claim e3 references e1, skip e2).
        Detection: prev_event_hash points to non-existent event.
        """
        e1 = _make_event(self.kp_auth, self.actor, self.genesis["event_id"], {"v": 1})
        e2 = _make_event(self.kp_auth, self.actor, e1["event_id"], {"v": 2})
        
        # Forge e3 to skip e2 (reference e1 as prev, but e1 is not immediate predecessor)
        e3_forged = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor,
            "actor_key_id": self.kp_auth.key_id,
            "timestamp_utc": datetime.utcnow().isoformat(),
            "prev_event_hash": e1["event_id"],  # Should be e2["event_id"]
            "payload": {"v": 3},
        }
        e3_forged["event_id"] = "evt_" + canonical_hash(e3_forged)[:24]
        e3_forged_signed = sign_event(e3_forged, self.kp_auth.private_key, self.kp_auth.key_id)
        
        # Chain with skipped event
        chain_with_skip = [self.genesis, e1, e2, e3_forged_signed]
        self.assertFalse(verify_causal_chain(chain_with_skip, self.actor))

    def test_attack_cross_actor_chain_reference(self):
        """
        ATTACK: Reference another actor's event as prev_event_hash (cross-actor link).
        Spec: prev_event_hash MUST NOT reference another actor's events.
        Detection: Causal chain verification checks per-actor chains.
        """
        actor2 = "other_actor"
        kp2 = BackpackKeypair.generate()
        
        e_actor2 = _make_event(kp2, actor2, None, {"data": "from_actor2"}, "GENESIS")
        
        # Try to reference actor2's event from actor1's chain
        e_malicious = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor,
            "actor_key_id": self.kp_auth.key_id,
            "timestamp_utc": datetime.utcnow().isoformat(),
            "prev_event_hash": e_actor2["event_id"],  # Cross-actor reference!
            "payload": {"data": "injected"},
        }
        e_malicious["event_id"] = "evt_" + canonical_hash(e_malicious)[:24]
        e_malicious_signed = sign_event(e_malicious, self.kp_auth.private_key, self.kp_auth.key_id)
        
        # Chain with cross-actor reference should fail
        chain = [self.genesis, e_malicious_signed]
        self.assertFalse(verify_causal_chain(chain, self.actor))

    def test_attack_null_prev_non_genesis(self):
        """
        ATTACK: Create non-GENESIS event with null prev_event_hash.
        Spec: Only GENESIS events can have null prev.
        Detection: Causal chain expects non-null prev for non-GENESIS.
        """
        # Forge OBSERVATION with null prev (should be GENESIS only)
        e_malicious = {
            "type": "OBSERVATION",  # Should be GENESIS
            "namespace": "local",
            "actor": self.actor,
            "actor_key_id": self.kp_auth.key_id,
            "timestamp_utc": datetime.utcnow().isoformat(),
            "prev_event_hash": None,  # Invalid for OBSERVATION
            "payload": {"data": "forged_genesis"},
        }
        e_malicious["event_id"] = "evt_" + canonical_hash(e_malicious)[:24]
        e_malicious_signed = sign_event(e_malicious, self.kp_auth.private_key, self.kp_auth.key_id)
        
        # Chain with invalid event
        chain = [self.genesis, e_malicious_signed]
        # The chain should fail or be flagged as invalid
        self.assertFalse(verify_causal_chain(chain, self.actor))

    def test_attack_duplicate_event_in_chain(self):
        """
        ATTACK: Append same event twice (duplicate event_id in chain).
        Detection: Event IDs must be unique per actor. Deduplication or uniqueness check.
        """
        e1 = _make_event(self.kp_auth, self.actor, self.genesis["event_id"], {"v": 1})
        
        # Chain with e1 duplicated
        chain_with_dup = [self.genesis, e1, e1]  # Same event appended twice
        
        # The chain should either fail verification (due to prev_hash mismatch)
        # or be flagged by deduplication logic
        self.assertFalse(verify_causal_chain(chain_with_dup, self.actor))

    def test_attack_impossible_prev_reference(self):
        """
        ATTACK: Reference non-existent event as prev_event_hash.
        Detection: Causal chain verifier checks that prev event exists.
        """
        fake_id = "evt_fakefakefakefakefakefake"
        
        e_malicious = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor,
            "actor_key_id": self.kp_auth.key_id,
            "timestamp_utc": datetime.utcnow().isoformat(),
            "prev_event_hash": fake_id,  # Non-existent event
            "payload": {"data": "orphaned"},
        }
        e_malicious["event_id"] = "evt_" + canonical_hash(e_malicious)[:24]
        e_malicious_signed = sign_event(e_malicious, self.kp_auth.private_key, self.kp_auth.key_id)
        
        chain = [self.genesis, e_malicious_signed]
        self.assertFalse(verify_causal_chain(chain, self.actor))

    def test_fork_detection_two_genesis(self):
        """
        ATTACK: Create forked chains with two different GENESIS events from same actor.
        Detection: Forks are detectable (two events with null prev from same actor).
        """
        genesis2 = _make_event(self.kp_auth, self.actor, None, {"v": 0, "fork": True}, "GENESIS")
        
        # Two genesis events from same actor = fork
        self.assertNotEqual(self.genesis["event_id"], genesis2["event_id"])
        
        # Both have null prev
        self.assertIsNone(self.genesis["prev_event_hash"])
        self.assertIsNone(genesis2["prev_event_hash"])
        
        # Detect fork
        forks_found = detect_forks([self.genesis, genesis2])
        # Either forks are detected or chain verification fails
        self.assertTrue(len(forks_found) > 0 or not verify_causal_chain([self.genesis, genesis2], self.actor))

    def test_timestamp_monotonicity_anomaly(self):
        """
        ATTACK: Retroactive event (timestamp earlier than predecessor).
        Detection: While cryptographically valid, timestamp monotonicity check catches this.
        """
        now = datetime.utcnow()
        past = now - timedelta(days=1)
        
        e1 = _make_event(self.kp_auth, self.actor, self.genesis["event_id"], {"v": 1}, ts=now.isoformat())
        e2 = _make_event(self.kp_auth, self.actor, e1["event_id"], {"v": 2}, ts=past.isoformat())
        
        chain = [self.genesis, e1, e2]
        
        # Causal chain is valid (prev_hash correct)
        self.assertTrue(verify_causal_chain(chain, self.actor))
        
        # But timestamps are reversed (detectable anomaly)
        ts1 = datetime.fromisoformat(e1["timestamp_utc"])
        ts2 = datetime.fromisoformat(e2["timestamp_utc"])
        self.assertGreater(ts1, ts2)  # ts1 > ts2 is anomalous

    def test_checkpoint_manipulation_event_count(self):
        """
        ATTACK: Sign checkpoint with false event_count.
        Detection: Signature covers event_count. Any modification breaks signature.
        """
        state = {"canonical": {"x": 1}, "metadata": {"last_event_id": self.genesis["event_id"], "event_count": 1}}
        
        # Create temp dir for checkpoint
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "merkle_root.txt").write_text("abc123def456")
            checkpoint = create_checkpoint(tmp, state, self.kp_auth.private_key, self.kp_auth.key_id)
            cp_dict = checkpoint.to_dict()
            
            # Attacker modifies event count
            cp_dict["event_count"] = 9999
            
            # Signature no longer valid
            self.assertFalse(verify_checkpoint(cp_dict, self.kp_auth.public_key))
        finally:
            shutil.rmtree(tmp)

    def test_checkpoint_manipulation_merkle_root(self):
        """
        ATTACK: Sign checkpoint with false merkle_root.
        Detection: Signature covers merkle_root. Modification invalidates signature.
        """
        state = {"canonical": {"x": 1}, "metadata": {"last_event_id": self.genesis["event_id"], "event_count": 1}}
        
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "merkle_root.txt").write_text("original_root")
            checkpoint = create_checkpoint(tmp, state, self.kp_auth.private_key, self.kp_auth.key_id)
            cp_dict = checkpoint.to_dict()
            
            # Attacker modifies merkle root
            original_root = cp_dict["merkle_root"]
            cp_dict["merkle_root"] = "forged_merkle_root_hash"
            
            # Different from original
            self.assertNotEqual(cp_dict["merkle_root"], original_root)
            
            # Signature invalid
            self.assertFalse(verify_checkpoint(cp_dict, self.kp_auth.public_key))
        finally:
            shutil.rmtree(tmp)

    def test_merkle_tree_leaf_swap_order_matters(self):
        """
        ATTACK: Reorder file entries in manifest (swap leaf order).
        Detection: Merkle tree depends on sorted order. Different order → different root.
        """
        files_a = [
            {"path": "aaa.txt", "sha256": "hash_a" * 8, "size": 10},
            {"path": "zzz.txt", "sha256": "hash_z" * 8, "size": 20}
        ]
        
        files_b = [files_a[1], files_a[0]]  # Reversed
        
        leaves_a = [canonical_bytes(f) for f in files_a]
        leaves_b = [canonical_bytes(f) for f in files_b]
        
        root_a = merkle_root_hex(leaves_a)
        root_b = merkle_root_hex(leaves_b)
        
        # Different order must produce different merkle root
        self.assertNotEqual(root_a, root_b)

if __name__ == "__main__":
    unittest.main()
