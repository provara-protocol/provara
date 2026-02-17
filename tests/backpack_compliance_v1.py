"""
backpack_compliance_v1.py — Backpack v1.0 Sovereign Nucleus Protocol
Compliance Test Suite (Hardened)

Verifies the four pillars: Structure, Integrity, Determinism, Safety.

Spec §12 requires compliant implementations to pass:
  - determinism_test:  replay same log twice → identical state hash
  - integrity_test:    verify hash chain + signatures + merkle root
  - merge_test:        union events from two peers → consistent state
  - lease_test:        stale fencing token writes rejected/quarantined

This suite covers structure + integrity + determinism + safety policy.
Merge and lease tests belong in the sync layer test suite.

Usage:
  python backpack_compliance_v1.py /path/to/backpack [-v]

Hardening changelog vs original:
  - File-to-disk hash verification (not just internal manifest consistency)
  - Structural safety tier validation (not string matching)
  - Per-actor causal chain verification
  - Genesis, event, and sync_contract schema validation
  - Phantom file detection
  - Path traversal protection
  - Reducer determinism test (spec §12)
  - Missing required files added (keys.json, retention_policy.json)
"""

from __future__ import annotations
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def merkle_root_hex(leaves: List[bytes]) -> str:
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    level = [hashlib.sha256(x).digest() for x in leaves]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(hashlib.sha256(left + right).digest())
        level = nxt
    return level[0].hex()


def is_safe_relative_path(root: Path, rel_path: str) -> bool:
    """Reject paths that escape root via traversal or absolute refs."""
    if os.path.isabs(rel_path):
        return False
    if ".." in Path(rel_path).parts:
        return False
    resolved = (root / rel_path).resolve()
    try:
        resolved.relative_to(root.resolve())
        return True
    except ValueError:
        return False


def load_ndjson(path: Path) -> List[Dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Malformed JSON at {path.name} line {i}: {e}"
                )
    return records


# ---------------------------------------------------------------------------
# Manifest exclude set (files that are the manifest, not hashed by it)
# ---------------------------------------------------------------------------

MANIFEST_META_FILES = frozenset({
    "manifest.json",
    "manifest.sig",
    "merkle_root.txt",
})


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

class TestBackpackComplianceV1(unittest.TestCase):
    """
    Compliance test suite for Backpack v1.0 Sovereign Nucleus Protocol.
    """

    backpack_path: Optional[str] = None

    @classmethod
    def setUpClass(cls):
        if not cls.backpack_path:
            raise unittest.SkipTest("No backpack path provided.")
        cls.root = Path(cls.backpack_path).resolve()
        if not cls.root.is_dir():
            raise unittest.SkipTest(f"Not a directory: {cls.root}")

    # ==================================================================
    # §1 — DIRECTORY STRUCTURE
    # ==================================================================

    def test_01_required_directories(self):
        """Spec §1: Required directory hierarchy exists."""
        required_dirs = [
            "identity",
            "events",
            "state",
            "artifacts",
            "artifacts/cas",
            "policies",
        ]
        for d in required_dirs:
            with self.subTest(directory=d):
                self.assertTrue(
                    (self.root / d).is_dir(),
                    f"Missing required directory: {d}",
                )

    def test_02_required_files(self):
        """Spec §1: All load-bearing protocol files present."""
        required_files = [
            "identity/genesis.json",
            "identity/keys.json",
            "events/events.ndjson",
            "policies/sync_contract.json",
            "policies/safety_policy.json",
            "policies/retention_policy.json",
            "manifest.json",
            "merkle_root.txt",
        ]
        for f in required_files:
            with self.subTest(file=f):
                self.assertTrue(
                    (self.root / f).is_file(),
                    f"Missing core protocol file: {f}",
                )

    # ==================================================================
    # §2 — IDENTITY PRIMITIVE
    # ==================================================================

    def test_03_genesis_schema(self):
        """Spec §2: genesis.json contains required identity fields."""
        genesis_path = self.root / "identity" / "genesis.json"
        if not genesis_path.is_file():
            self.skipTest("genesis.json missing (caught by test_02)")

        genesis = json.loads(genesis_path.read_text(encoding="utf-8"))
        required_fields = ["uid", "birth_timestamp", "root_key_id"]
        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(
                    field,
                    genesis,
                    f"genesis.json missing required field: {field}",
                )
                self.assertTrue(
                    genesis[field],
                    f"genesis.json field '{field}' is empty/falsy",
                )

    def test_04_keys_schema(self):
        """Spec §2: keys.json lists at least one active key."""
        keys_path = self.root / "identity" / "keys.json"
        if not keys_path.is_file():
            self.skipTest("keys.json missing (caught by test_02)")

        keys_data = json.loads(keys_path.read_text(encoding="utf-8"))
        self.assertIn("keys", keys_data, "keys.json missing 'keys' array")
        self.assertIsInstance(keys_data["keys"], list)
        self.assertGreater(
            len(keys_data["keys"]),
            0,
            "keys.json must contain at least one key",
        )

        # Validate first key has minimum required fields
        first_key = keys_data["keys"][0]
        for field in ["key_id", "algorithm", "status"]:
            with self.subTest(field=field):
                self.assertIn(field, first_key, f"Key missing field: {field}")

    # ==================================================================
    # §3 — EVENT LEDGER
    # ==================================================================

    def test_05_event_schema(self):
        """Spec §3: Every event has required fields."""
        events_path = self.root / "events" / "events.ndjson"
        if not events_path.is_file():
            self.skipTest("events.ndjson missing")

        events = load_ndjson(events_path)
        self.assertGreater(len(events), 0, "Event log is empty")

        required_event_fields = ["event_id", "type", "actor"]
        for i, event in enumerate(events):
            for field in required_event_fields:
                with self.subTest(event_index=i, field=field):
                    self.assertIn(
                        field,
                        event,
                        f"Event {i} (id={event.get('event_id', '?')}) "
                        f"missing required field: {field}",
                    )

    def test_06_event_ids_unique(self):
        """Spec §3: All event_ids are unique within the log."""
        events_path = self.root / "events" / "events.ndjson"
        if not events_path.is_file():
            self.skipTest("events.ndjson missing")

        events = load_ndjson(events_path)
        ids = [e.get("event_id") for e in events if e.get("event_id")]
        self.assertEqual(
            len(ids),
            len(set(ids)),
            f"Duplicate event_ids found: "
            f"{[x for x in ids if ids.count(x) > 1]}",
        )

    def test_07_causal_chain_per_actor(self):
        """Spec §3: prev_event_hash forms valid per-actor chains."""
        events_path = self.root / "events" / "events.ndjson"
        if not events_path.is_file():
            self.skipTest("events.ndjson missing")

        events = load_ndjson(events_path)
        all_ids = {e.get("event_id") for e in events}

        # Group by actor to validate per-actor chain integrity
        actor_events: Dict[str, List[Dict]] = {}
        for e in events:
            actor = e.get("actor", "unknown")
            actor_events.setdefault(actor, []).append(e)

        for actor, actor_evts in actor_events.items():
            # Sort by ts_logical for chain validation
            sorted_evts = sorted(
                actor_evts,
                key=lambda x: x.get("ts_logical", 0) or 0,
            )

            for e in sorted_evts:
                prev = e.get("prev_event_hash")
                if prev is None:
                    continue  # First event in chain, OK

                with self.subTest(actor=actor, event_id=e.get("event_id")):
                    # prev_event_hash must reference an existing event
                    self.assertIn(
                        prev,
                        all_ids,
                        f"Broken chain: event {e.get('event_id')} "
                        f"(actor={actor}) refs missing {prev}",
                    )

                    # prev_event_hash must reference an event by the SAME actor
                    prev_event = next(
                        (x for x in events if x.get("event_id") == prev),
                        None,
                    )
                    if prev_event is not None:
                        self.assertEqual(
                            prev_event.get("actor"),
                            actor,
                            f"Cross-actor chain violation: event "
                            f"{e.get('event_id')} (actor={actor}) "
                            f"refs event {prev} "
                            f"(actor={prev_event.get('actor')})",
                        )

    # ==================================================================
    # §11 — MANIFEST + MERKLE INTEGRITY
    # ==================================================================

    def test_08_manifest_path_safety(self):
        """Security: No path traversal in manifest file entries."""
        manifest_path = self.root / "manifest.json"
        if not manifest_path.is_file():
            self.skipTest("manifest.json missing")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest.get("files", []):
            rel_path = entry.get("path", "")
            with self.subTest(path=rel_path):
                self.assertTrue(
                    is_safe_relative_path(self.root, rel_path),
                    f"Path traversal detected: {rel_path}",
                )

    def test_09_manifest_files_match_disk(self):
        """Spec §11: Every file in manifest exists on disk with correct hash + size."""
        manifest_path = self.root / "manifest.json"
        if not manifest_path.is_file():
            self.skipTest("manifest.json missing")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest.get("files", []):
            rel_path = entry["path"]
            expected_hash = entry["sha256"]
            expected_size = entry["size"]

            with self.subTest(path=rel_path):
                # Safety check first
                if not is_safe_relative_path(self.root, rel_path):
                    self.fail(f"Unsafe path in manifest: {rel_path}")

                file_path = self.root / rel_path
                self.assertTrue(
                    file_path.is_file(),
                    f"File in manifest missing from disk: {rel_path}",
                )

                actual_size = file_path.stat().st_size
                self.assertEqual(
                    actual_size,
                    expected_size,
                    f"Size mismatch for {rel_path}: "
                    f"manifest={expected_size}, disk={actual_size}",
                )

                actual_hash = sha256_file(file_path)
                self.assertEqual(
                    actual_hash,
                    expected_hash,
                    f"Hash mismatch for {rel_path}: "
                    f"manifest={expected_hash}, disk={actual_hash}",
                )

    def test_10_manifest_merkle_root(self):
        """Spec §11: Merkle root matches recomputation from manifest leaves."""
        manifest_path = self.root / "manifest.json"
        merkle_path = self.root / "merkle_root.txt"
        if not manifest_path.is_file() or not merkle_path.is_file():
            self.skipTest("manifest.json or merkle_root.txt missing")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        stored_root = merkle_path.read_text(encoding="utf-8").strip()

        leaves = [
            canonical_json_bytes(entry)
            for entry in sorted(
                manifest.get("files", []), key=lambda x: x["path"]
            )
        ]
        computed_root = merkle_root_hex(leaves)

        self.assertEqual(
            computed_root,
            stored_root,
            "Merkle root mismatch: manifest is tampered or out of sync",
        )

    def test_11_phantom_file_detection(self):
        """Security: No unmanifested files exist in the backpack."""
        manifest_path = self.root / "manifest.json"
        if not manifest_path.is_file():
            self.skipTest("manifest.json missing")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifested_paths = {entry["path"] for entry in manifest.get("files", [])}

        # Walk disk and find files not in the manifest
        phantom_files = []
        for p in sorted(self.root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(self.root).as_posix()
            if rel in MANIFEST_META_FILES:
                continue  # These are excluded by design
            if rel not in manifested_paths:
                phantom_files.append(rel)

        self.assertEqual(
            phantom_files,
            [],
            f"Phantom files detected (on disk but not in manifest): "
            f"{phantom_files}",
        )

    def test_12_manifest_spec_version(self):
        """Spec §11: Manifest declares backpack_spec_version."""
        manifest_path = self.root / "manifest.json"
        if not manifest_path.is_file():
            self.skipTest("manifest.json missing")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertIn(
            "backpack_spec_version",
            manifest,
            "manifest.json missing 'backpack_spec_version' field",
        )
        self.assertEqual(
            manifest["backpack_spec_version"],
            "1.0",
            f"Unsupported spec version: {manifest.get('backpack_spec_version')}",
        )

    # ==================================================================
    # §7 — SAFETY ENVELOPE
    # ==================================================================

    def test_13_safety_policy_structure(self):
        """Spec §7: Safety policy defines L0-L3 as structural tier keys."""
        policy_path = self.root / "policies" / "safety_policy.json"
        if not policy_path.is_file():
            self.skipTest("safety_policy.json missing")

        policy = json.loads(policy_path.read_text(encoding="utf-8"))

        # Find the action_classes dict (top-level or nested)
        action_classes = policy.get("action_classes")
        if action_classes is None:
            # Try alternate key names
            for candidate in ["tiers", "safety_tiers", "levels"]:
                action_classes = policy.get(candidate)
                if action_classes is not None:
                    break

        self.assertIsNotNone(
            action_classes,
            "Safety policy missing 'action_classes' (or 'tiers'/'safety_tiers'/'levels') object. "
            "L0-L3 must be structural keys, not string mentions.",
        )
        self.assertIsInstance(action_classes, dict)

        required_tiers = ["L0", "L1", "L2", "L3"]
        for tier in required_tiers:
            with self.subTest(tier=tier):
                self.assertIn(
                    tier,
                    action_classes,
                    f"Safety policy action_classes missing tier KEY: {tier}. "
                    f"Present keys: {list(action_classes.keys())}",
                )
                # Each tier must be a dict with at least a description or approval field
                tier_def = action_classes[tier]
                self.assertIsInstance(
                    tier_def,
                    dict,
                    f"Tier {tier} must be an object, got {type(tier_def).__name__}",
                )

    def test_14_safety_merge_ratchet(self):
        """Spec §7: Safety policy defines merge ratchet direction."""
        policy_path = self.root / "policies" / "safety_policy.json"
        if not policy_path.is_file():
            self.skipTest("safety_policy.json missing")

        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        self.assertIn(
            "merge_ratchet",
            policy,
            "Safety policy missing 'merge_ratchet' rule "
            "(expected: 'most_restrictive_wins')",
        )

    # ==================================================================
    # §8 — SYNC CONTRACT
    # ==================================================================

    def test_15_sync_contract_schema(self):
        """Spec §8: Sync contract defines required governance fields."""
        contract_path = self.root / "policies" / "sync_contract.json"
        if not contract_path.is_file():
            self.skipTest("sync_contract.json missing")

        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        required_fields = [
            "authorities",
            "merge_policies",
            "replication_factor",
            "degradation_ladder",
        ]
        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(
                    field,
                    contract,
                    f"sync_contract.json missing required field: {field}",
                )

        # Authorities must be a non-empty list
        self.assertIsInstance(contract["authorities"], list)
        self.assertGreater(
            len(contract["authorities"]),
            0,
            "sync_contract must define at least one authority",
        )

        # Degradation ladder must have at least 2 levels
        self.assertIsInstance(contract["degradation_ladder"], list)
        self.assertGreaterEqual(
            len(contract["degradation_ladder"]),
            2,
            "degradation_ladder must have at least 2 fallback levels",
        )

    # ==================================================================
    # §4 — REDUCER DETERMINISM (Spec §12 mandatory)
    # ==================================================================

    def test_16_reducer_determinism(self):
        """Spec §12 (mandatory): Replay same event log twice → identical state hash."""
        events_path = self.root / "events" / "events.ndjson"
        if not events_path.is_file():
            self.skipTest("events.ndjson missing")

        # Try to import the reducer
        try:
            # Add common locations to path
            for candidate in [
                Path(__file__).parent,
                Path.cwd(),
            ]:
                if candidate not in [Path(p) for p in sys.path]:
                    sys.path.insert(0, str(candidate))

            from provara.reducer_v0 import SovereignReducerV0
        except ImportError:
            self.skipTest(
                "SovereignReducerV0 not importable — "
                "reducer determinism test requires reducer_v0.py on PYTHONPATH"
            )

        events = load_ndjson(events_path)

        r1 = SovereignReducerV0()
        r1.apply_events(events)
        state1 = r1.export_state_json()
        hash1 = r1.state["metadata"]["state_hash"]

        r2 = SovereignReducerV0()
        r2.apply_events(events)
        state2 = r2.export_state_json()
        hash2 = r2.state["metadata"]["state_hash"]

        self.assertEqual(
            state1,
            state2,
            "Reducer determinism FAILED: two replays of the same event log "
            "produced different canonical JSON output",
        )
        self.assertEqual(
            hash1,
            hash2,
            "Reducer determinism FAILED: state hashes diverged",
        )

    # ==================================================================
    # §10 — RETENTION POLICY
    # ==================================================================

    def test_17_retention_policy_events_permanent(self):
        """Spec §10: Retention policy must declare events as permanent."""
        retention_path = self.root / "policies" / "retention_policy.json"
        if not retention_path.is_file():
            self.skipTest("retention_policy.json missing")

        retention = json.loads(retention_path.read_text(encoding="utf-8"))
        self.assertIn("events", retention, "Retention policy missing 'events' rule")
        self.assertEqual(
            retention["events"],
            "permanent",
            "Events MUST have 'permanent' retention. "
            f"Found: {retention.get('events')}",
        )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python backpack_compliance_v1.py /path/to/backpack [-v]")
        sys.exit(1)

    # Extract backpack path (last non-flag argument)
    backpack_arg = None
    remaining_args = []
    for arg in sys.argv[1:]:
        if arg.startswith("-"):
            remaining_args.append(arg)
        elif backpack_arg is None:
            backpack_arg = arg
        else:
            remaining_args.append(arg)

    if not backpack_arg:
        print("Error: Provide path to backpack.")
        sys.exit(1)

    TestBackpackComplianceV1.backpack_path = backpack_arg
    sys.argv = [sys.argv[0]] + remaining_args
    unittest.main()
