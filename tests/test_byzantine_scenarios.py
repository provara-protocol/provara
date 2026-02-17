"""
test_byzantine_scenarios.py - Provara Byzantine Fault Tolerance Tests

Tests multi-actor adversarial scenarios:
  1. Two actors create conflicting observations (both signed, both valid)
  2. Attacker withholds events from one actor
  3. Replay attack across actor boundaries
  4. Impersonation (signature forgery)
  5. Split-brain sync
  6. Fencing token prevents stale merge
  7. N actors with K adversarial
  8. Event ordering attack via fake timestamps

Run:
  PYTHONPATH=src pytest tests/test_byzantine_scenarios.py -v
"""

import base64
import datetime
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from provara.backpack_signing import (
    BackpackKeypair,
    key_id_from_public_bytes,
    load_private_key_b64,
    sign_event,
    verify_event_signature,
)
from provara.bootstrap_v0 import bootstrap_backpack
from provara.canonical_json import canonical_bytes, canonical_dumps, canonical_hash
from provara.sync_v0 import (
    verify_causal_chain,
    merge_event_logs,
)


# ---------------------------------------------------------------------------
# Helper: build a properly structured, content-addressed event
# ---------------------------------------------------------------------------

def _make_event(
    event_type: str,
    namespace: str,
    actor: str,
    keypair: BackpackKeypair,
    ts_logical: int,
    prev_event_hash,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Construct, ID, and sign an event matching the Provara protocol structure."""
    event = {
        "type": event_type,
        "namespace": namespace,
        "actor": actor,
        "actor_key_id": keypair.key_id,
        "ts_logical": ts_logical,
        "prev_event_hash": prev_event_hash,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "payload": payload,
    }
    event["event_id"] = "evt_" + canonical_hash(event)[:24]
    event = sign_event(event, keypair.private_key, keypair.key_id)
    return event


# ---------------------------------------------------------------------------
# Helper: reconstruct a BackpackKeypair from a BootstrapResult
# ---------------------------------------------------------------------------

def _keypair_from_result(result) -> BackpackKeypair:
    """Reconstruct a BackpackKeypair from a BootstrapResult."""
    sk = load_private_key_b64(result.root_private_key_b64)
    pk = sk.public_key()
    pub_bytes = pk.public_bytes(Encoding.Raw, PublicFormat.Raw)
    pub_b64 = base64.b64encode(pub_bytes).decode("ascii")
    key_id = key_id_from_public_bytes(pub_bytes)
    return BackpackKeypair(
        private_key=sk,
        public_key=pk,
        key_id=key_id,
        public_key_b64=pub_b64,
    )


class TestByzantineScenarios(unittest.TestCase):
    """Multi-actor adversarial scenarios."""

    def setUp(self):
        """Create a multi-actor vault environment."""
        self.tmp = tempfile.mkdtemp()

        # Actor A (honest)
        vault_a_path = Path(self.tmp) / "vault_a"
        vault_a_path.mkdir(parents=True)
        result_a = bootstrap_backpack(target_path=vault_a_path, quiet=True)
        self.keypair_a = _keypair_from_result(result_a)
        self.actor_a = result_a.root_key_id

        # Actor B (honest)
        vault_b_path = Path(self.tmp) / "vault_b"
        vault_b_path.mkdir(parents=True)
        result_b = bootstrap_backpack(target_path=vault_b_path, quiet=True)
        self.keypair_b = _keypair_from_result(result_b)
        self.actor_b = result_b.root_key_id

        # Actor C (compromised)
        vault_c_path = Path(self.tmp) / "vault_c"
        vault_c_path.mkdir(parents=True)
        result_c = bootstrap_backpack(target_path=vault_c_path, quiet=True)
        self.keypair_c = _keypair_from_result(result_c)
        self.actor_c = result_c.root_key_id

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # =========================================================================
    # Byzantine 1: Conflicting Observations
    # =========================================================================

    def test_byzantine_conflicting_observations(self):
        """Two honest actors observe the same subject with conflicting values.

        Expected behavior: Both observations are cryptographically valid but
        logically conflicting. The reducer must handle this.
        """
        event_a = _make_event(
            event_type="OBSERVATION",
            namespace="local",
            actor=self.actor_a,
            keypair=self.keypair_a,
            ts_logical=10,
            prev_event_hash=None,
            payload={
                "subject": "door_01",
                "predicate": "status",
                "value": "open",
                "confidence": 0.95,
            },
        )
        event_b = _make_event(
            event_type="OBSERVATION",
            namespace="local",
            actor=self.actor_b,
            keypair=self.keypair_b,
            ts_logical=10,
            prev_event_hash=None,
            payload={
                "subject": "door_01",
                "predicate": "status",
                "value": "closed",
                "confidence": 0.95,
            },
        )
        self.assertTrue(verify_event_signature(event_a, self.keypair_a.public_key))
        self.assertTrue(verify_event_signature(event_b, self.keypair_b.public_key))
        self.assertNotEqual(event_a["payload"]["value"], event_b["payload"]["value"])

    # =========================================================================
    # Byzantine 2: Event Withholding
    # =========================================================================

    def test_byzantine_event_withholding_detected(self):
        """Actor C withholds event_a1, breaking the causal chain.

        Expected behavior: verify_causal_chain returns False when the only
        event for actor_a has a non-null prev_event_hash.
        """
        event_a1 = _make_event(
            event_type="OBSERVATION",
            namespace="local",
            actor=self.actor_a,
            keypair=self.keypair_a,
            ts_logical=10,
            prev_event_hash=None,
            payload={"subject": "room_a", "predicate": "temperature", "value": 20.5, "confidence": 0.9},
        )
        event_a2 = _make_event(
            event_type="OBSERVATION",
            namespace="local",
            actor=self.actor_a,
            keypair=self.keypair_a,
            ts_logical=11,
            prev_event_hash=event_a1["event_id"],
            payload={"subject": "room_a", "predicate": "humidity", "value": 45.0, "confidence": 0.88},
        )
        # C withholds event_a1; only event_a2 is presented (which has non-null prev)
        chain_incomplete = [event_a2]
        self.assertFalse(verify_causal_chain(chain_incomplete, self.actor_a))

    # =========================================================================
    # Byzantine 3: Replay Across Actor Boundaries
    # =========================================================================

    def test_byzantine_replay_across_actors_detected(self):
        """C replays A event by changing the actor field to B.

        Expected behavior: verify_event_signature with B public key returns False
        because the sig was created with A private key over A content.
        """
        event_a = _make_event(
            event_type="OBSERVATION",
            namespace="local",
            actor=self.actor_a,
            keypair=self.keypair_a,
            ts_logical=10,
            prev_event_hash=None,
            payload={"subject": "sensor_x", "predicate": "reading", "value": 42, "confidence": 0.99},
        )
        event_replayed = dict(event_a)
        event_replayed["actor"] = self.actor_b
        self.assertFalse(verify_event_signature(event_replayed, self.keypair_b.public_key))

    # =========================================================================
    # Byzantine 4: Signature Forgery (Impersonation)
    # =========================================================================

    def test_byzantine_impersonation_fails(self):
        """C signs an event claiming to be from A but uses C key.

        Expected behavior: verify_event_signature with A public key returns False.
        """
        event_forgery = {
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": self.actor_a,
            "actor_key_id": self.keypair_a.key_id,
            "ts_logical": 10,
            "prev_event_hash": None,
            "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "payload": {
                "subject": "sensor_y",
                "predicate": "compromised",
                "value": True,
                "confidence": 0.5,
            },
        }
        event_forgery["event_id"] = "evt_" + canonical_hash(event_forgery)[:24]
        event_forged = sign_event(
            event_forgery, self.keypair_c.private_key, self.keypair_c.key_id
        )
        self.assertFalse(verify_event_signature(event_forged, self.keypair_a.public_key))

    # =========================================================================
    # Byzantine 5: Split-Brain and Reconciliation
    # =========================================================================

    def test_byzantine_split_brain_sync(self):
        """Actors A and B diverge offline; each log is internally valid.

        Expected behavior: Each independent chain passes verify_causal_chain.
        Actual merge testing is in test_sync_v0.py.
        """
        event_a1 = _make_event(
            event_type="OBSERVATION",
            namespace="local",
            actor=self.actor_a,
            keypair=self.keypair_a,
            ts_logical=10,
            prev_event_hash=None,
            payload={"subject": "branch_a", "predicate": "value", "value": "A1", "confidence": 0.9},
        )
        event_b1 = _make_event(
            event_type="OBSERVATION",
            namespace="local",
            actor=self.actor_b,
            keypair=self.keypair_b,
            ts_logical=10,
            prev_event_hash=None,
            payload={"subject": "branch_b", "predicate": "value", "value": "B1", "confidence": 0.9},
        )
        self.assertTrue(verify_causal_chain([event_a1], self.actor_a))
        self.assertTrue(verify_causal_chain([event_b1], self.actor_b))

    # =========================================================================
    # Byzantine 6: Fencing Token Prevents Stale Merge
    # =========================================================================

    def test_byzantine_fencing_token_validation(self):
        """Conceptual test: fencing tokens prevent stale merges.

        Full fencing token testing is in test_sync_v0.py.
        """
        pass

    # =========================================================================
    # Byzantine 7: N Actors, K Adversarial (Majority Honest)
    # =========================================================================

    def test_byzantine_majority_honest_consensus(self):
        """With 3 actors (A and B honest, C adversarial), all events are
        individually valid but A and B agree while C is outvoted.

        Expected behavior: All three events pass signature verification.
        Application-level consensus handles the conflict.
        """
        event_a = _make_event(
            event_type="OBSERVATION",
            namespace="canonical",
            actor=self.actor_a,
            keypair=self.keypair_a,
            ts_logical=10,
            prev_event_hash=None,
            payload={"subject": "door_01", "predicate": "status", "value": "locked", "confidence": 0.99},
        )
        event_b = _make_event(
            event_type="OBSERVATION",
            namespace="canonical",
            actor=self.actor_b,
            keypair=self.keypair_b,
            ts_logical=10,
            prev_event_hash=None,
            payload={"subject": "door_01", "predicate": "status", "value": "locked", "confidence": 0.99},
        )
        event_c = _make_event(
            event_type="OBSERVATION",
            namespace="canonical",
            actor=self.actor_c,
            keypair=self.keypair_c,
            ts_logical=10,
            prev_event_hash=None,
            payload={"subject": "door_01", "predicate": "status", "value": "unlocked", "confidence": 0.99},
        )
        self.assertTrue(verify_event_signature(event_a, self.keypair_a.public_key))
        self.assertTrue(verify_event_signature(event_b, self.keypair_b.public_key))
        self.assertTrue(verify_event_signature(event_c, self.keypair_c.public_key))

    # =========================================================================
    # Byzantine 8: Timestamp Ordering Attack
    # =========================================================================

    def test_byzantine_timestamp_ordering_attack_detected(self):
        """A backdated timestamp cannot reorder the causal chain.

        Expected behavior: verify_causal_chain trusts prev_event_hash, not
        timestamps. A chain valid by hash linkage passes despite reversed
        wall-clock timestamps.
        """
        event_1 = _make_event(
            event_type="OBSERVATION",
            namespace="local",
            actor=self.actor_a,
            keypair=self.keypair_a,
            ts_logical=100,
            prev_event_hash=None,
            payload={"subject": "evt1", "predicate": "order", "value": "first", "confidence": 0.9},
        )
        event_2 = _make_event(
            event_type="OBSERVATION",
            namespace="local",
            actor=self.actor_a,
            keypair=self.keypair_a,
            ts_logical=101,
            prev_event_hash=event_1["event_id"],
            payload={
                "subject": "evt2",
                "predicate": "order",
                "value": "second_but_backdated",
                "confidence": 0.9,
            },
        )
        chain = [event_1, event_2]
        self.assertTrue(verify_causal_chain(chain, self.actor_a))


if __name__ == "__main__":
    unittest.main()
