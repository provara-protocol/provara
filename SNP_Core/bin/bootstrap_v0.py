"""
bootstrap_v0.py — Backpack v1.0 Sovereign Bootstrap

Creates a fully compliant, cryptographically signed backpack from nothing.
One command → a mesh-ready sovereign node.

What it produces:
  identity/genesis.json       — Birth certificate with root key ID
  identity/keys.json          — Key registry (root + optional quorum)
  events/events.ndjson        — Seed event log (signed GENESIS + OBSERVATION)
  policies/sync_contract.json — Governance and authority ladder
  policies/safety_policy.json — L0-L3 kinetic risk tiers
  policies/retention_policy.json — Data permanence rules
  policies/ontology/perception_ontology_v1.json — Initial perception model
  state/                      — Empty (regeneratable by reducer)
  artifacts/cas/              — Empty (populated by sensor pipeline)
  manifest.json               — Deterministic file index
  merkle_root.txt             — Integrity anchor
  manifest.sig                — Ed25519 signature over manifest

Exit criteria:
  The output backpack MUST pass all 17 compliance tests. If it doesn't,
  the bootstrap has a bug.

Usage:
  python bootstrap_v0.py /path/to/new_backpack [options]

  Options:
    --uid TEXT           Custom UID (default: generated UUIDv4)
    --actor TEXT         Actor name for genesis events (default: "sovereign_genesis")
    --quorum             Also generate a quorum keypair
    --private-keys FILE  Write private keys to this file (default: stdout warning)
    --self-test          Run compliance suite after bootstrap (requires test suite)
    --quiet              Suppress progress output

Dependencies:
  - backpack_signing.py (Ed25519 primitives)
  - canonical_json.py (deterministic serialization)
  - manifest_generator.py (manifest + merkle root)
"""

from __future__ import annotations
import argparse
import datetime
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure sibling imports work when run from bin/ or project root
_this_dir = Path(__file__).resolve().parent
if str(_this_dir) not in sys.path:
    sys.path.insert(0, str(_this_dir))

from canonical_json import canonical_bytes, canonical_dumps, canonical_hash
from backpack_signing import (
    BackpackKeypair,
    sign_event,
    sign_manifest,
)


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Event construction
# ---------------------------------------------------------------------------

def _build_signed_event(
    event_type: str,
    payload: Dict[str, Any],
    actor: str,
    namespace: str,
    ts_logical: int,
    prev_event_hash: Optional[str],
    keypair: BackpackKeypair,
) -> Dict[str, Any]:
    """Build a content-addressed, signed event."""
    event = {
        "type": event_type,
        "namespace": namespace,
        "actor": actor,
        "actor_key_id": keypair.key_id,
        "ts_logical": ts_logical,
        "prev_event_hash": prev_event_hash,
        "timestamp_utc": _utc_now(),
        "payload": payload,
    }
    # Content-addressed ID (hash of everything except event_id and sig)
    event["event_id"] = f"evt_{canonical_hash(event)[:24]}"
    # Sign
    event = sign_event(event, keypair.private_key, keypair.key_id)
    return event


# ---------------------------------------------------------------------------
# Policy templates
# ---------------------------------------------------------------------------

def _default_safety_policy() -> Dict[str, Any]:
    return {
        "action_classes": {
            "L0": {
                "description": "data-only/reversible",
                "offline_allowed": True,
                "approval": "local_reducer",
            },
            "L1": {
                "description": "low-kinetic",
                "offline_allowed": True,
                "approval": "local_reducer+policy",
                "review_on_sync": True,
            },
            "L2": {
                "description": "high-kinetic",
                "offline_allowed": "within_lease",
                "approval": "multi_sensor+signed_policy",
            },
            "L3": {
                "description": "irreversible/human-space",
                "offline_allowed": False,
                "approval": "remote_signature_or_mfa",
            },
        },
        "merge_ratchet": "most_restrictive_wins",
        "loosen_requires": "signed_policy_update_by_top_authority",
    }


def _default_sync_contract(
    root_key_id: str,
    quorum_key_id: Optional[str] = None,
) -> Dict[str, Any]:
    authorities = [
        {"role": "root", "key_id": root_key_id, "scope": "all"},
    ]
    if quorum_key_id:
        authorities.append(
            {"role": "quorum", "key_id": quorum_key_id, "scope": "attestation"}
        )
    return {
        "authorities": authorities,
        "merge_policies": {
            "events": "union_by_event_id",
            "beliefs": "evidence_union_then_reduce",
            "policies": "authority_signed_update",
        },
        "lease_model": {
            "default_duration_seconds": 300,
            "fencing": True,
        },
        "replication_factor": 2,
        "degradation_ladder": [
            "designated_human",
            "quorum_peers",
            "archive_peer",
            "local_emergency",
        ],
    }


def _default_retention_policy() -> Dict[str, Any]:
    return {
        "events": "permanent",
        "checkpoints": "permanent",
        "perception_t0_raw": {
            "max_age_days": 30,
            "eviction": "oldest_first",
        },
        "artifacts_cas": {
            "referenced_by_event": "permanent",
            "unreferenced": {"max_age_days": 90},
        },
        "state_caches": "regeneratable_on_eviction",
    }


def _default_ontology() -> Dict[str, Any]:
    return {
        "version": "v1",
        "object_classes": [
            "door", "mug", "person", "container",
            "surface", "tool", "obstacle",
        ],
    }


# ---------------------------------------------------------------------------
# Manifest generation (inline to avoid circular dependency)
# ---------------------------------------------------------------------------

def _generate_manifest(root: Path) -> tuple:
    """Generate manifest.json and merkle_root.txt. Returns (manifest_dict, root_hex)."""
    import hashlib

    EXCLUDE = {"manifest.json", "manifest.sig", "merkle_root.txt"}
    files = []

    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel in EXCLUDE:
            continue
        # Path safety
        if ".." in Path(rel).parts:
            continue
        # Hash + size
        h = hashlib.sha256()
        with p.open("rb") as f:
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    break
                h.update(chunk)
        files.append({
            "path": rel,
            "sha256": h.hexdigest(),
            "size": p.stat().st_size,
        })

    manifest = {
        "backpack_spec_version": "1.0",
        "manifest_version": "manifest.v0",
        "file_count": len(files),
        "created_at_utc": _utc_now(),
        "files": files,
    }

    # Merkle root
    leaves = [canonical_bytes(entry) for entry in files]
    if not leaves:
        root_hex = hashlib.sha256(b"").hexdigest()
    else:
        level = [hashlib.sha256(x).digest() for x in leaves]
        while len(level) > 1:
            nxt = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else level[i]
                nxt.append(hashlib.sha256(left + right).digest())
            level = nxt
        root_hex = level[0].hex()

    return manifest, root_hex


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

class BootstrapResult:
    """Result of a sovereign bootstrap operation."""

    def __init__(self):
        self.success: bool = False
        self.backpack_path: Optional[Path] = None
        self.uid: Optional[str] = None
        self.root_key_id: Optional[str] = None
        self.quorum_key_id: Optional[str] = None
        self.root_private_key_b64: Optional[str] = None
        self.quorum_private_key_b64: Optional[str] = None
        self.genesis_event_id: Optional[str] = None
        self.seed_event_id: Optional[str] = None
        self.file_count: int = 0
        self.merkle_root: Optional[str] = None
        self.errors: List[str] = []
        self.compliance_passed: Optional[bool] = None

    def __repr__(self):
        status = "SUCCESS" if self.success else "FAILED"
        return f"BootstrapResult({status}, uid={self.uid}, key={self.root_key_id})"


def bootstrap_backpack(
    target_path: Path,
    uid: Optional[str] = None,
    actor: str = "sovereign_genesis",
    include_quorum: bool = False,
    quiet: bool = False,
) -> BootstrapResult:
    """
    Birth a fully compliant Backpack v1.0 from nothing.

    Args:
        target_path: Directory to create the backpack in. Must not exist or be empty.
        uid: Custom UID. If None, a UUIDv4 is generated.
        actor: Actor name for genesis events.
        include_quorum: Also generate a quorum keypair.
        quiet: Suppress progress output.

    Returns:
        BootstrapResult with all generated identifiers and key material.
    """
    result = BootstrapResult()
    result.backpack_path = target_path

    def log(msg: str):
        if not quiet:
            print(f"  [bootstrap] {msg}")

    # ---- Validate target ----
    if target_path.exists() and any(target_path.iterdir()):
        result.errors.append(f"Target directory is not empty: {target_path}")
        return result

    # ---- Generate identity ----
    log("Generating Ed25519 root keypair...")
    root_kp = BackpackKeypair.generate()
    result.root_key_id = root_kp.key_id
    result.root_private_key_b64 = root_kp.private_key_b64()

    quorum_kp = None
    if include_quorum:
        log("Generating Ed25519 quorum keypair...")
        quorum_kp = BackpackKeypair.generate()
        result.quorum_key_id = quorum_kp.key_id
        result.quorum_private_key_b64 = quorum_kp.private_key_b64()

    result.uid = uid or str(uuid.uuid4())

    # ---- Create directory structure ----
    log("Creating directory structure...")
    dirs = [
        "identity",
        "events",
        "state",
        "artifacts/cas",
        "policies/ontology",
    ]
    for d in dirs:
        (target_path / d).mkdir(parents=True, exist_ok=True)

    # ---- Write genesis.json ----
    log("Writing genesis.json...")
    genesis = {
        "uid": result.uid,
        "birth_timestamp": _utc_now(),
        "root_key_id": root_kp.key_id,
        "governance_model": "policies/sync_contract.json",
        "initial_ontology_versions": {
            "perception": "perception_ontology_v1.json",
        },
    }
    _write_json(target_path / "identity" / "genesis.json", genesis)

    # ---- Write keys.json ----
    log("Writing keys.json...")
    keys_list = [root_kp.to_keys_entry(roles=["root", "attestation"])]
    if quorum_kp:
        keys_list.append(
            quorum_kp.to_keys_entry(roles=["quorum", "attestation"])
        )
    keys_data = {"keys": keys_list, "revocations": []}
    _write_json(target_path / "identity" / "keys.json", keys_data)

    # ---- Write policies ----
    log("Writing policy files...")
    _write_json(
        target_path / "policies" / "safety_policy.json",
        _default_safety_policy(),
    )
    _write_json(
        target_path / "policies" / "sync_contract.json",
        _default_sync_contract(
            root_kp.key_id,
            quorum_kp.key_id if quorum_kp else None,
        ),
    )
    _write_json(
        target_path / "policies" / "retention_policy.json",
        _default_retention_policy(),
    )
    _write_json(
        target_path / "policies" / "ontology" / "perception_ontology_v1.json",
        _default_ontology(),
    )

    # ---- Write seed events ----
    log("Writing seed events...")
    events_path = target_path / "events" / "events.ndjson"

    # Event 1: GENESIS (birth certificate in the ledger)
    genesis_event = _build_signed_event(
        event_type="GENESIS",
        payload={
            "uid": result.uid,
            "root_key_id": root_kp.key_id,
            "birth_timestamp": genesis["birth_timestamp"],
            "spec_version": "1.0",
        },
        actor=actor,
        namespace="canonical",
        ts_logical=1,
        prev_event_hash=None,
        keypair=root_kp,
    )
    result.genesis_event_id = genesis_event["event_id"]

    # Event 2: OBSERVATION (system initialization — proves reducer works)
    seed_event = _build_signed_event(
        event_type="OBSERVATION",
        payload={
            "subject": "system",
            "predicate": "status",
            "value": "initialized",
            "confidence": 1.0,
        },
        actor=actor,
        namespace="local",
        ts_logical=2,
        prev_event_hash=genesis_event["event_id"],
        keypair=root_kp,
    )
    result.seed_event_id = seed_event["event_id"]

    # Write events
    with events_path.open("w", encoding="utf-8") as f:
        f.write(canonical_dumps(genesis_event) + "\n")
        f.write(canonical_dumps(seed_event) + "\n")

    # ---- Generate manifest + merkle root ----
    log("Generating manifest and Merkle root...")
    manifest, merkle_hex = _generate_manifest(target_path)
    result.file_count = manifest["file_count"]
    result.merkle_root = merkle_hex

    # Write manifest (canonical JSON for determinism)
    (target_path / "manifest.json").write_text(
        canonical_dumps(manifest), encoding="utf-8"
    )
    (target_path / "merkle_root.txt").write_text(
        merkle_hex + "\n", encoding="utf-8"
    )

    # ---- Sign manifest ----
    log("Signing manifest...")
    sig_record = sign_manifest(
        target_path / "manifest.json",
        target_path / "merkle_root.txt",
        root_kp.private_key,
        root_kp.key_id,
    )
    _write_json(target_path / "manifest.sig", sig_record)

    result.success = True
    log(f"Bootstrap complete. UID={result.uid}")
    log(f"Root key: {root_kp.key_id}")
    if quorum_kp:
        log(f"Quorum key: {quorum_kp.key_id}")
    log(f"Files: {result.file_count} | Merkle: {merkle_hex[:16]}...")

    return result


def _write_json(path: Path, data: Any) -> None:
    """Write JSON with consistent formatting."""
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Self-test: run compliance suite against bootstrapped backpack
# ---------------------------------------------------------------------------

def run_self_test(backpack_path: Path, quiet: bool = False) -> bool:
    """Run the 17-test compliance suite against a backpack. Returns True if all pass."""
    import unittest
    import io

    try:
        from backpack_compliance_v1 import TestBackpackComplianceV1
    except ImportError:
        # Try finding it in test/ relative to this file
        test_dir = _this_dir.parent / "test"
        if str(test_dir) not in sys.path:
            sys.path.insert(0, str(test_dir))
        try:
            from backpack_compliance_v1 import TestBackpackComplianceV1
        except ImportError:
            if not quiet:
                print("  [self-test] Compliance suite not found. Skipping.")
            return False

    TestBackpackComplianceV1.backpack_path = str(backpack_path)
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestBackpackComplianceV1)

    if quiet:
        stream = io.StringIO()
        runner = unittest.TextTestRunner(stream=stream, verbosity=0)
    else:
        runner = unittest.TextTestRunner(verbosity=2)

    result = runner.run(suite)
    return result.wasSuccessful()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Backpack v1.0 Sovereign Bootstrap — Birth a new node",
        epilog="Private keys are printed to stdout. Pipe to a secure file.",
    )
    ap.add_argument(
        "target",
        help="Directory to create the backpack in",
    )
    ap.add_argument(
        "--uid",
        default=None,
        help="Custom UID (default: UUIDv4)",
    )
    ap.add_argument(
        "--actor",
        default="sovereign_genesis",
        help="Actor name for genesis events",
    )
    ap.add_argument(
        "--quorum",
        action="store_true",
        help="Also generate a quorum keypair",
    )
    ap.add_argument(
        "--private-keys",
        default=None,
        help="Write private keys to this file instead of stdout",
    )
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="Run compliance suite after bootstrap",
    )
    ap.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output",
    )

    args = ap.parse_args()
    target = Path(args.target)

    result = bootstrap_backpack(
        target_path=target,
        uid=args.uid,
        actor=args.actor,
        include_quorum=args.quorum,
        quiet=args.quiet,
    )

    if not result.success:
        print(f"BOOTSTRAP FAILED: {result.errors}", file=sys.stderr)
        sys.exit(1)

    # Output private keys
    key_output = {
        "WARNING": "PRIVATE KEYS — DO NOT STORE IN THE BACKPACK",
        "root": {
            "key_id": result.root_key_id,
            "private_key_b64": result.root_private_key_b64,
        },
    }
    if result.quorum_key_id:
        key_output["quorum"] = {
            "key_id": result.quorum_key_id,
            "private_key_b64": result.quorum_private_key_b64,
        }

    if args.private_keys:
        pk_path = Path(args.private_keys)
        pk_path.write_text(
            json.dumps(key_output, indent=2) + "\n",
            encoding="utf-8",
        )
        if not args.quiet:
            print(f"  [bootstrap] Private keys written to: {pk_path}")
    else:
        if not args.quiet:
            print("\n  ⚠  PRIVATE KEYS (do NOT store in the backpack):")
            print(json.dumps(key_output, indent=2))

    # Self-test
    if args.self_test:
        if not args.quiet:
            print("\n  [self-test] Running compliance suite...")
        passed = run_self_test(target, quiet=args.quiet)
        result.compliance_passed = passed
        if passed:
            if not args.quiet:
                print("  [self-test] ✓ All compliance tests passed.")
        else:
            print("  [self-test] ✗ COMPLIANCE FAILED.", file=sys.stderr)
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
