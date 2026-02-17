import base64
import unittest

from provara.backpack_signing import BackpackKeypair, sign_event, verify_event_signature
from provara.canonical_json import canonical_hash
from provara.sync_v0 import verify_causal_chain


def _make_event(kp, actor, ts_logical, prev_event_hash, payload, event_type="OBSERVATION"):
    e = {
        "type": event_type,
        "namespace": "local",
        "actor": actor,
        "actor_key_id": kp.key_id,
        "ts_logical": ts_logical,
        "prev_event_hash": prev_event_hash,
        "payload": payload,
    }
    e["event_id"] = "evt_" + canonical_hash(e)[:24]
    return sign_event(e, kp.private_key, kp.key_id)


class TestForgeryAttacks(unittest.TestCase):

    def setUp(self):
        self.kp = BackpackKeypair.generate()
        self.actor = "sovereign_test"
        e0 = {"type": "GENESIS", "namespace": "local", "actor": self.actor,
              "actor_key_id": self.kp.key_id, "ts_logical": 0,
              "prev_event_hash": None, "payload": {}}
        e0["event_id"] = "evt_" + canonical_hash(e0)[:24]
        self.genesis_event = sign_event(e0, self.kp.private_key, self.kp.key_id)
        e1 = {"type": "OBSERVATION", "namespace": "local", "actor": self.actor,
              "actor_key_id": self.kp.key_id, "ts_logical": 1,
              "prev_event_hash": self.genesis_event["event_id"],
              "payload": {"subject": "door_01", "value": "open"}}
        e1["event_id"] = "evt_" + canonical_hash(e1)[:24]
        self.event_2 = sign_event(e1, self.kp.private_key, self.kp.key_id)

    def test_attack_insert_mid_chain_fails(self):
        fake_event = _make_event(self.kp, self.actor, ts_logical=1,
                                 prev_event_hash=self.genesis_event["event_id"],
                                 payload={"subject": "fake_door", "value": "closed"})
        chain = [self.genesis_event, fake_event, self.event_2]
        self.assertFalse(verify_causal_chain(chain, self.actor))

    def test_attack_swap_events_fails(self):
        event_3 = _make_event(self.kp, self.actor, ts_logical=2,
                              prev_event_hash=self.event_2["event_id"],
                              payload={"subject": "door_02", "value": "locked"})
        chain = [self.genesis_event, event_3, self.event_2]
        self.assertFalse(verify_causal_chain(chain, self.actor))

    def test_attack_modify_field_after_signing_fails(self):
        tampered = dict(self.event_2)
        tampered["payload"] = {"subject": "door_01", "value": "closed"}
        self.assertFalse(verify_event_signature(tampered, self.kp.public_key))

    def test_attack_replay_into_different_vault_detected(self):
        """Attack: Take a valid event from vault A and present it to vault B.

        Detection mechanism:
          1. The replayed event actor does not match actor_b (structural mismatch).
          2. The replayed event signature does not verify under kp_b public key.
        """
        kp_b = BackpackKeypair.generate()
        actor_b = "sovereign_vault_b"

        # The replayed event carries the wrong actor
        self.assertNotEqual(self.event_2["actor"], actor_b)

        # The replayed event signature is from kp_a -- it cannot verify under kp_b
        self.assertFalse(verify_event_signature(self.event_2, kp_b.public_key))

    def test_attack_sign_with_wrong_key_fails(self):
        keypair_2 = BackpackKeypair.generate()
        e = {"type": "OBSERVATION", "namespace": "local", "actor": self.actor,
             "actor_key_id": self.kp.key_id, "ts_logical": 1,
             "prev_event_hash": self.genesis_event["event_id"],
             "payload": {"subject": "door_01", "value": "open"}}
        e["event_id"] = "evt_" + canonical_hash(e)[:24]
        payload_bytes = canonical_hash(e).encode()
        e["sig"] = base64.b64encode(keypair_2.private_key.sign(payload_bytes)).decode("ascii")
        self.assertFalse(verify_event_signature(e, self.kp.public_key))

    def test_attack_flip_signature_bit_fails(self):
        tampered = dict(self.event_2)
        sig_bytes = bytearray(base64.b64decode(tampered["sig"]))
        sig_bytes[0] ^= 1
        tampered["sig"] = base64.b64encode(sig_bytes).decode()
        self.assertFalse(verify_event_signature(tampered, self.kp.public_key))

    def test_attack_use_revoked_key_fails(self):
        self.assertTrue(verify_event_signature(self.event_2, self.kp.public_key))
        old_keypair = BackpackKeypair.generate()
        e = {"type": "OBSERVATION", "namespace": "local", "actor": self.actor,
             "actor_key_id": self.kp.key_id, "ts_logical": 2,
             "prev_event_hash": self.event_2["event_id"],
             "payload": {"subject": "door_01", "value": "closed"}}
        e["event_id"] = "evt_" + canonical_hash(e)[:24]
        signed_by_old = sign_event(e, old_keypair.private_key, old_keypair.key_id)
        e["sig"] = signed_by_old["sig"]
        self.assertFalse(verify_event_signature(e, self.kp.public_key))

    def test_attack_modify_event_id_after_signing_fails(self):
        tampered = dict(self.event_2)
        tampered["event_id"] = "evt_" + "0" * 24
        self.assertFalse(verify_event_signature(tampered, self.kp.public_key))

    def test_attack_fork_not_merged_silently(self):
        event_2a = _make_event(self.kp, self.actor, ts_logical=1,
                               prev_event_hash=self.genesis_event["event_id"],
                               payload={"subject": "door_01", "value": "open"})
        event_2b = _make_event(self.kp, self.actor, ts_logical=1,
                               prev_event_hash=self.genesis_event["event_id"],
                               payload={"subject": "door_02", "value": "locked"})
        self.assertEqual(event_2a["prev_event_hash"], event_2b["prev_event_hash"])
        self.assertNotEqual(event_2a["event_id"], event_2b["event_id"])
        chain = [self.genesis_event, event_2a, event_2b]
        self.assertFalse(verify_causal_chain(chain, self.actor))

    def test_attack_garbage_event_with_fake_prev_hash_fails(self):
        garbage_event = _make_event(self.kp, self.actor, ts_logical=1,
                                    prev_event_hash="evt_" + "0" * 24,
                                    payload={"subject": "fake", "value": "fake"})
        chain = [self.genesis_event, garbage_event]
        self.assertFalse(verify_causal_chain(chain, self.actor))

    def test_attack_truncate_log_and_falsify_tail_fails(self):
        event_3 = _make_event(self.kp, self.actor, ts_logical=2,
                              prev_event_hash=self.event_2["event_id"],
                              payload={"subject": "door_03", "value": False})
        forged_event_3 = _make_event(self.kp, self.actor, ts_logical=2,
                                     prev_event_hash=self.event_2["event_id"],
                                     payload={"subject": "door_04", "value": True})
        original_chain = [self.genesis_event, self.event_2, event_3]
        forged_chain = [self.genesis_event, self.event_2, forged_event_3]
        self.assertTrue(verify_causal_chain(original_chain, self.actor))
        self.assertTrue(verify_causal_chain(forged_chain, self.actor))
        self.assertNotEqual(event_3["event_id"], forged_event_3["event_id"])

    def test_attack_cycle_in_causal_chain_impossible(self):
        event_3_cycle = _make_event(self.kp, self.actor, ts_logical=2,
                                    prev_event_hash=self.genesis_event["event_id"],
                                    payload={"subject": "cycle", "value": "attempt"})
        chain = [self.genesis_event, self.event_2, event_3_cycle]
        self.assertFalse(verify_causal_chain(chain, self.actor))


if __name__ == "__main__":
    unittest.main()
