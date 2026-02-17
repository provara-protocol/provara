#!/usr/bin/env python3
"""
provara.py — Unified CLI for Provara Protocol v1.0

Commands:
  init      Create a new Memory Vault (Backpack)
  verify    Run all integrity and compliance checks
  backup    Create an integrity-verified timestamped backup
  manifest  Regenerate manifest.json and Merkle root
  checkpoint Create a signed state snapshot for faster loading
  replay    Show current derived belief state
  append    Append a signed observation or assertion
"""

from __future__ import annotations
import argparse
import json
import os
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Core imports
from .bootstrap_v0 import bootstrap_backpack
from .backpack_signing import (
    load_private_key_b64,
    load_keys_registry,
    resolve_public_key,
    key_id_from_public_bytes,
    sign_event,
)
from .canonical_json import canonical_dumps, canonical_hash
from .manifest_generator import build_manifest, manifest_leaves
from .backpack_integrity import merkle_root_hex, MANIFEST_EXCLUDE, canonical_json_bytes
from .reducer_v0 import SovereignReducerV0
from .checkpoint_v0 import create_checkpoint, save_checkpoint, load_latest_checkpoint, verify_checkpoint
from .sync_v0 import load_events, write_events

# Repo root: src/provara/../../  (two levels up from this file's directory)
_repo_root = Path(__file__).resolve().parents[2]

def _get_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")

def cmd_init(args: argparse.Namespace) -> None:
    target = Path(args.path).resolve()
    keys_file = Path(args.private_keys or "my_private_keys.json").resolve()
    
    print(f"Initializing Provara Vault at: {target}")
    # Fix: bootstrap_backpack uses 'actor', not 'actor_name'
    # Also Path(args.path) should be passed as Path or string
    result = bootstrap_backpack(
        target,
        uid=args.uid,
        actor=args.actor or "sovereign_genesis",
        include_quorum=args.quorum,
        quiet=False
    )
    
    # result is a BootstrapResult object, not a dict
    if result.success:
        print("\nSUCCESS: Vault created and verified.")
        if args.private_keys:
            # bootstrap_backpack doesn't take private_keys_path, we need to save them
            keys = {
                result.root_key_id: result.root_private_key_b64
            }
            if result.quorum_key_id:
                keys[result.quorum_key_id] = result.quorum_private_key_b64
            keys_file.write_text(json.dumps(keys, indent=2))
            print(f"Private keys saved to: {keys_file}")
        else:
            print("\nIMPORTANT: Your private keys were printed to stdout (default bootstrap behavior).")
        print("IMPORTANT: Secure your private keys. If lost, vault access is permanent read-only.")
    else:
        print("\nERROR: Bootstrap failed.")
        sys.exit(1)

def cmd_verify(args: argparse.Namespace) -> None:
    target = Path(args.path).resolve()
    sys.path.insert(0, str(_repo_root / "tests"))
    from backpack_compliance_v1 import TestBackpackComplianceV1
    import unittest
    
    print(f"Verifying vault integrity: {target}")
    TestBackpackComplianceV1.backpack_path = str(target)
    
    # Create a test suite with the compliance tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestBackpackComplianceV1)
    
    # Run the tests quietly or verbosely
    verbosity = 2 if args.verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\nPASS: All 17 integrity checks passed.")
    else:
        print("\nFAIL: Integrity checks failed.")
        sys.exit(1)

def cmd_backup(args: argparse.Namespace) -> None:
    vault = Path(args.path).resolve()
    backup_dir = Path(args.to or "Backups").resolve()
    max_backups = args.keep
    
    if not vault.is_dir():
        print(f"Error: Vault not found at {vault}")
        sys.exit(1)
        
    print(f"Backing up vault: {vault}")
    
    # 1. Verify before backup
    sys.path.insert(0, str(_repo_root / "tests"))
    from backpack_compliance_v1 import TestBackpackComplianceV1
    import unittest
    
    TestBackpackComplianceV1.backpack_path = str(vault)
    suite = unittest.TestLoader().loadTestsFromTestCase(TestBackpackComplianceV1)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    if not result.wasSuccessful():
        print("Error: Source vault integrity check failed. Backup aborted.")
        sys.exit(1)
        
    # 2. Create zip
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = _get_timestamp()
    zip_path = backup_dir / f"Backup_{ts}.zip"
    
    print(f"Creating archive: {zip_path}")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(vault):
            for file in files:
                p = Path(root) / file
                zf.write(p, arcname=p.relative_to(vault.parent))
                
    # 3. Hash
    import hashlib
    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (backup_dir / f"Backup_{ts}.sha256").write_text(f"{sha}  {zip_path.name}\n")
    
    # 4. Prune
    all_backups = sorted(backup_dir.glob("Backup_*.zip"))
    if len(all_backups) > max_backups:
        to_remove = all_backups[:-max_backups]
        for b in to_remove:
            print(f"Pruning old backup: {b.name}")
            b.unlink()
            h = b.with_suffix(".sha256")
            if h.exists(): h.unlink()
            
    print(f"\nSUCCESS: Backup complete and verified. (Hash: {sha[:16]}...)")

def cmd_manifest(args: argparse.Namespace) -> None:
    root = Path(args.path).resolve()
    exclude = set(MANIFEST_EXCLUDE)
    
    print(f"Regenerating manifest for: {root}")
    manifest = build_manifest(root, exclude)
    leaves = manifest_leaves(manifest)
    root_hex = merkle_root_hex(leaves)
    
    (root / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    (root / "merkle_root.txt").write_text(root_hex + "\n", encoding="utf-8")
    
    print(f"manifest_file_count: {manifest['file_count']}")
    print(f"merkle_root: {root_hex}")

def _load_keys(keys_path: Path) -> Dict[str, str]:
    if not keys_path.exists():
        print(f"Error: Private keys file not found at {keys_path}")
        sys.exit(1)
    data = json.loads(keys_path.read_text())
    return {str(k): str(v) for k, v in data.items()}

def cmd_checkpoint(args: argparse.Namespace) -> None:
    vault = Path(args.path).resolve()
    keys_data = _load_keys(Path(args.keyfile))
    
    # Use first available key for signing checkpoint
    kid = list(keys_data.keys())[0]
    priv = load_private_key_b64(keys_data[kid])
    
    # Get current state
    events = load_events(vault / "events" / "events.ndjson")
    reducer = SovereignReducerV0()
    reducer.apply_events(events)
    state = reducer.export_state()
    
    cp = create_checkpoint(vault, state, priv, kid)
    cp_path = save_checkpoint(vault, cp)
    print(f"Checkpoint saved: {cp_path} (events={cp.event_count})")

def cmd_replay(args: argparse.Namespace) -> None:
    vault = Path(args.path).resolve()
    events = load_events(vault / "events" / "events.ndjson")
    
    reducer = SovereignReducerV0()
    reducer.apply_events(events)
    state = reducer.export_state()
    print(json.dumps(state, indent=2))

def cmd_append(args: argparse.Namespace) -> None:
    vault = Path(args.path).resolve()
    keys_data = _load_keys(Path(args.keyfile))
    
    # Use specified key or first available
    kid = args.key_id or list(keys_data.keys())[0]
    if kid not in keys_data:
        print(f"Error: Key {kid} not found in {args.keyfile}")
        sys.exit(1)
    priv = load_private_key_b64(keys_data[kid])
    
    # Load existing events to find prev_hash for this actor
    all_events = load_events(vault / "events" / "events.ndjson")
    actor_events = [e for e in all_events if e.get("actor_key_id") == kid]
    prev_hash = actor_events[-1].get("event_id") if actor_events else None
    
    # Build event
    if args.data.startswith("@"):
        path = Path(args.data[1:]).resolve()
        if not path.exists():
            print(f"Error: Data file not found: {path}")
            sys.exit(1)
        data_str = path.read_text(encoding="utf-8")
    else:
        data_str = args.data
        
    try:
        payload_data = json.loads(data_str)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON data: {e}")
        sys.exit(1)
        
    # Mapping for convenience (similar to psmc)
    subject = payload_data.get("subject") or "provara_cli"
    predicate = payload_data.get("predicate") or args.type
    
    event = {
        "type": args.type.upper(),
        "actor": args.actor or "provara_user",
        "prev_event_hash": prev_hash,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "subject": subject,
            "predicate": predicate,
            "value": payload_data,
            "confidence": float(args.confidence or 1.0)
        }
    }
    
    # Compute content-addressed ID: evt_ + SHA256(canonical_json(event_without_id_sig))[:24]
    eid_hash = canonical_hash(event)
    event["event_id"] = f"evt_{eid_hash[:24]}"
    
    # sign_event handles actor_key_id and sig
    signed = sign_event(event, priv, kid)
    
    # Append
    events_file = vault / "events" / "events.ndjson"
    with open(events_file, "a", encoding="utf-8") as f:
        f.write(canonical_dumps(signed) + "\n")
        
    print(f"Appended event {signed['event_id']} (type={signed['type']})")
    
    # Auto-regenerate manifest
    cmd_manifest(args)

def main() -> None:
    parser = argparse.ArgumentParser(prog="provara", description="Provara Protocol CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    
    # init
    p_init = sub.add_parser("init", help="Create a new vault")
    p_init.add_argument("path", help="Path to new vault")
    p_init.add_argument("--uid", help="Unique vault identifier")
    p_init.add_argument("--actor", help="Human-readable actor name")
    p_init.add_argument("--quorum", action="store_true", help="Generate recovery keypair")
    p_init.add_argument("--private-keys", help="Path to save private keys")
    
    # verify
    p_verify = sub.add_parser("verify", help="Verify vault integrity")
    p_verify.add_argument("path", help="Path to vault")
    p_verify.add_argument("-v", "--verbose", action="store_true")
    
    # backup
    p_backup = sub.add_parser("backup", help="Create verified backup")
    p_backup.add_argument("path", help="Path to vault")
    p_backup.add_argument("--to", default="Backups", help="Backup directory")
    p_backup.add_argument("--keep", type=int, default=12, help="Number of backups to retain")
    
    # manifest
    p_manifest = sub.add_parser("manifest", help="Regenerate manifest")
    p_manifest.add_argument("path", help="Path to vault")
    
    # checkpoint
    p_cp = sub.add_parser("checkpoint", help="Create state snapshot")
    p_cp.add_argument("path", help="Path to vault")
    p_cp.add_argument("--keyfile", required=True, help="Path to your private keys JSON")
    
    # replay
    p_replay = sub.add_parser("replay", help="Show derived belief state")
    p_replay.add_argument("path", help="Path to vault")

    # append
    p_app = sub.add_parser("append", help="Append a signed event")
    p_app.add_argument("path", help="Path to vault")
    p_app.add_argument("--type", required=True, help="Event type (e.g. OBSERVATION, ASSERTION)")
    p_app.add_argument("--data", required=True, help="JSON object for event data")
    p_app.add_argument("--keyfile", required=True, help="Path to your private keys JSON")
    p_app.add_argument("--key-id", help="Key ID to sign with (defaults to first)")
    p_app.add_argument("--actor", help="Human-readable actor identifier")
    p_app.add_argument("--confidence", type=float, help="Confidence score (0.0-1.0)")
    
    args = parser.parse_args()
    
    if args.command == "init": cmd_init(args)
    elif args.command == "verify": cmd_verify(args)
    elif args.command == "backup": cmd_backup(args)
    elif args.command == "manifest": cmd_manifest(args)
    elif args.command == "checkpoint": cmd_checkpoint(args)
    elif args.command == "replay": cmd_replay(args)
    elif args.command == "append": cmd_append(args)

if __name__ == "__main__":
    main()
