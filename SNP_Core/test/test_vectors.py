import unittest
import json
import base64
import sys
from pathlib import Path

# Add bin to sys.path
_this_dir = Path(__file__).resolve().parent
_bin_dir = _this_dir.parent / "bin"
if str(_bin_dir) not in sys.path:
    sys.path.insert(0, str(_bin_dir))

from canonical_json import canonical_bytes, canonical_hash
from backpack_signing import (
    load_public_key_b64, 
    verify_event_signature, 
    key_id_from_public_bytes
)
from backpack_integrity import merkle_root_hex
from reducer_v0 import SovereignReducerV0

class TestNormativeVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Path to vectors.json relative to project root
        cls.vectors_file = _this_dir.parent.parent / "test_vectors" / "vectors.json"
        if not cls.vectors_file.exists():
            raise FileNotFoundError(f"Missing vectors.json at {cls.vectors_file}")
        
        with open(cls.vectors_file, "r", encoding="utf-8") as f:
            cls.data = json.load(f)

    def test_canonical_json_vectors(self):
        for v in [v for v in self.data["vectors"] if v["id"].startswith("canonical_json")]:
            with self.subTest(vector_id=v["id"]):
                actual = canonical_bytes(v["input"]).hex()
                self.assertEqual(actual, v["expected"])

    def test_sha256_hash_vectors(self):
        for v in [v for v in self.data["vectors"] if v["id"].startswith("sha256_hash")]:
            with self.subTest(vector_id=v["id"]):
                actual = canonical_hash(v["input"])
                self.assertEqual(actual, v["expected"])

    def test_event_id_derivation_vectors(self):
        for v in [v for v in self.data["vectors"] if v["id"].startswith("event_id_derivation")]:
            with self.subTest(vector_id=v["id"]):
                # Derivation rule: evt_ + SHA256(canonical_json(event_without_id_sig))[:24]
                # v["input"] already has fields removed by generator script
                eid_hash = canonical_hash(v["input"])
                actual = f"evt_{eid_hash[:24]}"
                self.assertEqual(actual, v["expected"])

    def test_key_id_derivation_vectors(self):
        for v in [v for v in self.data["vectors"] if v["id"].startswith("key_id_derivation")]:
            with self.subTest(vector_id=v["id"]):
                pub_raw = bytes.fromhex(v["input"])
                actual = key_id_from_public_bytes(pub_raw)
                self.assertEqual(actual, v["expected"])

    def test_ed25519_sign_verify_vectors(self):
        for v in [v for v in self.data["vectors"] if v["id"].startswith("ed25519_sign_verify")]:
            with self.subTest(vector_id=v["id"]):
                # v["input"] = {"public_key_b64": ..., "message": ..., "key_id": ...}
                pk = load_public_key_b64(v["input"]["public_key_b64"])
                event = dict(v["input"]["message"])
                event["actor_key_id"] = v["input"]["key_id"]
                event["sig"] = v["expected"]
                
                self.assertTrue(verify_event_signature(event, pk))

    def test_merkle_root_vectors(self):
        for v in [v for v in self.data["vectors"] if v["id"].startswith("merkle_root")]:
            with self.subTest(vector_id=v["id"]):
                leaves = [canonical_bytes(e) for e in sorted(v["input"], key=lambda x: x["path"])]
                actual = merkle_root_hex(leaves)
                self.assertEqual(actual, v["expected"])

    def test_reducer_determinism_vectors(self):
        for v in [v for v in self.data["vectors"] if v["id"].startswith("reducer_determinism")]:
            with self.subTest(vector_id=v["id"]):
                reducer = SovereignReducerV0()
                reducer.apply_events(v["input"])
                actual = reducer.state["metadata"]["state_hash"]
                self.assertEqual(actual, v["expected"])

if __name__ == "__main__":
    unittest.main()
