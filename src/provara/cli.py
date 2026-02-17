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

def cmd_market_alpha(args: argparse.Namespace) -> None:
    from .market import record_market_alpha
    vault = Path(args.path).resolve()
    keys = Path(args.keyfile).resolve()
    signed = record_market_alpha(
        vault, keys, args.ticker, args.signal, args.conviction, args.horizon, args.rationale, args.actor
    )
    print(f"Recorded MARKET_ALPHA for {args.ticker}: {signed['event_id']}")

def cmd_hedge_fund_sim(args: argparse.Namespace) -> None:
    from .market import record_hedge_fund_sim
    vault = Path(args.path).resolve()
    keys = Path(args.keyfile).resolve()
    signed = record_hedge_fund_sim(
        vault, keys, args.sim_id, args.strategy, args.returns, args.ticker, args.actor
    )
    print(f"Recorded HEDGE_FUND_SIM for {args.strategy}: {signed['event_id']}")

def cmd_oracle_validate(args: argparse.Namespace) -> None:
    from .oracle import validate_market_alpha
    vault = Path(args.path).resolve()
    keys = Path(args.keyfile).resolve()
    results = validate_market_alpha(vault, keys, args.actor)
    if not results:
        print("No pending MARKET_ALPHA events found.")
    for r in results:
        print(f"ATTESTATION recorded: {r['event_id']} (Target: {r['payload']['target_event_id']})")

def cmd_resume(args: argparse.Namespace) -> None:
    from .resume import generate_resume
    vault = Path(args.path).resolve()
    print(generate_resume(vault))

def cmd_check_safety(args: argparse.Namespace) -> None:
    from . import Vault
    v = Vault(args.path)
    res = v.check_safety(args.action)
    print(f"Action: {args.action.upper()}")
    print(f"Status: {res['status']}")
    if 'tier' in res:
        print(f"Tier:   {res['tier']}")
    print(f"Reason: {res.get('reason') or res.get('description', '')}")

def cmd_wallet_export(args: argparse.Namespace) -> None:
    from .wallet import export_to_solana
    keys_data = _load_keys(Path(args.keyfile))
    kid = args.key_id or list(keys_data.keys())[0]
    priv_b64 = keys_data[kid]
    
    solana_keypair = export_to_solana(priv_b64)
    
    out_path = Path(args.out).resolve()
    out_path.write_text(json.dumps(solana_keypair), encoding="utf-8")
    print(f"Exported Provara key {kid} to Solana wallet: {out_path}")

def cmd_wallet_import(args: argparse.Namespace) -> None:
    from .wallet import import_from_solana
    in_path = Path(args.file).resolve()
    try:
        solana_kp = json.loads(in_path.read_text(encoding="utf-8"))
        res = import_from_solana(solana_kp)
    except Exception as e:
        print(f"Error importing Solana key: {e}")
        sys.exit(1)
        
    print("Imported Solana Key:")
    print(f"Key ID: {res['key_id']}")
    print(f"Private Key (Provara format): {res['private_key_b64']}")
    print("Add this to your keys.json to use it as an actor.")

def cmd_agent_loop(args: argparse.Namespace) -> None:
    from .agent_loop import run_alpha_loop
    vault = Path(args.path).resolve()
    keys = Path(args.keyfile).resolve()
    run_alpha_loop(vault, keys, args.actor, args.cycles)

def cmd_send_message(args: argparse.Namespace) -> None:
    from . import Vault
    v = Vault(args.path)
    keys_data = _load_keys(Path(args.keyfile))
    kid = args.key_id or list(keys_data.keys())[0]
    priv = keys_data[kid]
    sender_enc_priv = args.sender_encryption_private_key or priv
    
    # We need the recipient's public key
    # If not provided directly, we try to find it in the vault registry
    recip_pub = args.recipient_pubkey
    if not recip_pub:
        from .backpack_signing import load_keys_registry
        reg = load_keys_registry(v.path / "identity" / "keys.json")
        if args.recipient_id:
            entry = reg.get(args.recipient_id)
            if entry:
                pub = entry.get("public_key_b64")
                if isinstance(pub, str):
                    recip_pub = pub
    
    if not recip_pub:
        print("Error: Recipient public key or ID required.")
        sys.exit(1)
        
    # Read message from arg or file
    if args.message.startswith("@"):
        msg_str = Path(args.message[1:]).read_text(encoding="utf-8")
    else:
        msg_str = args.message
        
    msg_dict = json.loads(msg_str)
    
    res = v.send_message(
        kid,
        priv,
        sender_enc_priv,
        recip_pub,
        msg_dict,
        subject=args.subject,
    )
    print(f"Message sent! Event ID: {res['event_id']}")

def cmd_read_messages(args: argparse.Namespace) -> None:
    from . import Vault
    v = Vault(args.path)
    keys_data = _load_keys(Path(args.keyfile))
    kid = args.key_id or list(keys_data.keys())[0]
    my_enc_priv = args.my_encryption_private_key or keys_data[kid]
    
    messages = v.get_messages(my_enc_priv)
    if not messages:
        print("No messages found.")
        return
        
    print(f"--- Inbox for {kid} ---")
    for m in messages:
        print(f"\nFrom:    {m['from_actor']} ({m['from_key_id']})")
        print(f"Date:    {m['timestamp']}")
        print(f"Subject: {m['subject']}")
        print(f"Body:    {json.dumps(m['body'], indent=2)}")

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

    # market-alpha
    p_ma = sub.add_parser("market-alpha", help="Record a market signal")
    p_ma.add_argument("path", help="Path to vault")
    p_ma.add_argument("--ticker", required=True, help="e.g. BTC, NVDA")
    p_ma.add_argument("--signal", required=True, choices=["LONG", "SHORT", "NEUTRAL"])
    p_ma.add_argument("--conviction", type=float, default=0.5)
    p_ma.add_argument("--horizon", default="7d")
    p_ma.add_argument("--rationale")
    p_ma.add_argument("--keyfile", required=True)
    p_ma.add_argument("--actor", default="market_analyst")

    # hedge-fund-sim
    p_hf = sub.add_parser("hedge-fund-sim", help="Record simulation results")
    p_hf.add_argument("path", help="Path to vault")
    p_hf.add_argument("--sim-id", required=True)
    p_hf.add_argument("--strategy", required=True)
    p_hf.add_argument("--returns", type=float, required=True)
    p_hf.add_argument("--ticker")
    p_hf.add_argument("--keyfile", required=True)
    p_hf.add_argument("--actor", default="simulation_engine")

    # oracle-validate
    p_ov = sub.add_parser("oracle-validate", help="Scan and attest to market alpha performance")
    p_ov.add_argument("path", help="Path to vault")
    p_ov.add_argument("--keyfile", required=True)
    p_ov.add_argument("--actor", default="oracle_node_01")

    # resume
    p_res = sub.add_parser("resume", help="Generate verifiable agent resume")
    p_res.add_argument("path", help="Path to vault")

    # check-safety
    p_cs = sub.add_parser("check-safety", help="Evaluate action against safety policy")
    p_cs.add_argument("path", help="Path to vault")
    p_cs.add_argument("--action", required=True, help="Action to check (e.g. DELETE_VAULT, APPEND_OBSERVATION)")

    # wallet-export
    p_we = sub.add_parser("wallet-export", help="Export Provara key to Solana CLI format")
    p_we.add_argument("--keyfile", required=True)
    p_we.add_argument("--key-id", help="Specific Key ID to export")
    p_we.add_argument("--out", required=True, help="Output path for id.json")

    # wallet-import
    p_wi = sub.add_parser("wallet-import", help="Import Solana CLI keypair to Provara format")
    p_wi.add_argument("--file", required=True, help="Path to Solana id.json")

    # agent-loop
    p_loop = sub.add_parser("agent-loop", help="Run autonomous alpha engine loop")
    p_loop.add_argument("path", help="Path to vault")
    p_loop.add_argument("--keyfile", required=True)
    p_loop.add_argument("--actor", default="Alpha_Bot_01")
    p_loop.add_argument("--cycles", type=int, default=1)

    # send-message
    p_sm = sub.add_parser("send-message", help="Send encrypted message to another agent")
    p_sm.add_argument("path", help="Path to vault")
    p_sm.add_argument("--keyfile", required=True)
    p_sm.add_argument("--key-id", help="My Key ID")
    p_sm.add_argument("--recipient-id", help="Recipient's Key ID")
    p_sm.add_argument("--recipient-pubkey", help="Recipient's Public Key (B64)")
    p_sm.add_argument(
        "--sender-encryption-private-key",
        help="Sender X25519 private key (Base64). Defaults to selected key value.",
    )
    p_sm.add_argument("--message", required=True, help="Message JSON string or @file")
    p_sm.add_argument("--subject", help="Message subject")

    # read-messages
    p_rm = sub.add_parser("read-messages", help="Read and decrypt messages intended for me")
    p_rm.add_argument("path", help="Path to vault")
    p_rm.add_argument("--keyfile", required=True)
    p_rm.add_argument("--key-id", help="My Key ID")
    p_rm.add_argument(
        "--my-encryption-private-key",
        help="My X25519 private key (Base64). Defaults to selected key value.",
    )
    
    args = parser.parse_args()
    
    if args.command == "init": cmd_init(args)
    elif args.command == "verify": cmd_verify(args)
    elif args.command == "backup": cmd_backup(args)
    elif args.command == "manifest": cmd_manifest(args)
    elif args.command == "checkpoint": cmd_checkpoint(args)
    elif args.command == "replay": cmd_replay(args)
    elif args.command == "append": cmd_append(args)
    elif args.command == "market-alpha": cmd_market_alpha(args)
    elif args.command == "hedge-fund-sim": cmd_hedge_fund_sim(args)
    elif args.command == "oracle-validate": cmd_oracle_validate(args)
    elif args.command == "resume": cmd_resume(args)
    elif args.command == "check-safety": cmd_check_safety(args)
    elif args.command == "wallet-export": cmd_wallet_export(args)
    elif args.command == "wallet-import": cmd_wallet_import(args)
    elif args.command == "agent-loop": cmd_agent_loop(args)
    elif args.command == "send-message": cmd_send_message(args)
    elif args.command == "read-messages": cmd_read_messages(args)

    # ... after other subparsers ...
    # Wait, I need to add the actual subparser definitions too.

if __name__ == "__main__":
    main()
