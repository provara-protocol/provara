"""
archival.py — Vault Archival Rotation and Chain Verification

Implements the mechanism to seal a vault permanently and link it to a
successor vault, maintaining a continuous cryptographic chain of evidence
across storage boundaries.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .backpack_signing import load_private_key_b64, sign_event, resolve_public_key, load_keys_registry
from .canonical_json import canonical_dumps, canonical_hash
from .sync_v0 import load_events, iter_events
from .manifest_generator import build_manifest, manifest_leaves
from .backpack_integrity import merkle_root_hex, MANIFEST_EXCLUDE, validate_vault_structure
from .bootstrap_v0 import bootstrap_backpack

SEAL_EVENT_TYPE = "com.provara.vault.seal"

def is_vault_sealed(vault_path: Path) -> bool:
    """Check if a vault contains a seal event."""
    events_file = vault_path / "events" / "events.ndjson"
    if not events_file.exists():
        return False
    
    # Scan for seal event
    for event in iter_events(events_file):
        if event.get("type") == SEAL_EVENT_TYPE:
            return True
    return False

def seal_vault(vault_path: Path, keyfile_path: Path, reason: str = "archival_rotation") -> Dict[str, Any]:
    """Seal a vault permanently. Returns seal event."""
    if is_vault_sealed(vault_path):
        raise ValueError(f"Vault at {vault_path} is already sealed.")

    # 1. Load keys
    from .cli import _load_keys
    keys_data = _load_keys(keyfile_path)
    kid = list(keys_data.keys())[0]
    priv = load_private_key_b64(keys_data[kid])

    # 2. Get current state stats
    events_file = vault_path / "events" / "events.ndjson"
    all_events = load_events(events_file)
    event_count = len(all_events)
    
    # Generate current Merkle root
    exclude = set(MANIFEST_EXCLUDE)
    manifest = build_manifest(vault_path, exclude)
    leaves = manifest_leaves(manifest)
    root_hex = merkle_root_hex(leaves)

    # 3. Build Seal Event
    # We need prev_hash for the actor
    actor_name = "vault_archivist"
    actor_events = [e for e in all_events if e.get("actor") == actor_name]
    # Fallback to last event in log if archivist hasn't spoken yet
    prev_hash = actor_events[-1].get("event_id") if actor_events else all_events[-1].get("event_id")

    seal_payload = {
        "reason": reason,
        "final_event_count": event_count + 1, # Including this event
        "final_merkle_root": root_hex, # Merkle root of state BEING sealed
        "seal_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    event = {
        "type": SEAL_EVENT_TYPE,
        "actor": actor_name,
        "prev_event_hash": prev_hash,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "payload": seal_payload,
    }

    # Compute content-addressed ID
    eid_hash = canonical_hash(event)
    event["event_id"] = f"evt_{eid_hash[:24]}"
    
    # Sign
    signed = sign_event(event, priv, kid)
    
    # Append
    with open(events_file, "a", encoding="utf-8") as f:
        f.write(canonical_dumps(signed) + "\n")
    
    # Regenerate manifest.json and merkle_root.txt to include the seal event
    from .cli import cmd_manifest
    import argparse
    cmd_manifest(argparse.Namespace(path=str(vault_path)))
    
    return signed

def create_successor(
    sealed_vault_path: Path,
    successor_path: Path,
    keyfile_path: Path,
) -> Path:
    """Create a new vault linked to a sealed predecessor."""
    if not is_vault_sealed(sealed_vault_path):
        raise ValueError(f"Source vault at {sealed_vault_path} is NOT sealed. Seal it before rotating.")

    # 1. Extract predecessor info
    events_file = sealed_vault_path / "events" / "events.ndjson"
    all_events = load_events(events_file)
    seal_event = all_events[-1]
    
    if seal_event.get("type") != SEAL_EVENT_TYPE:
        # Scan if not last
        for e in reversed(all_events):
            if e.get("type") == SEAL_EVENT_TYPE:
                seal_event = e
                break
    
    merkle_root_path = sealed_vault_path / "merkle_root.txt"
    final_merkle_root = merkle_root_path.read_text(encoding="utf-8").strip()
    
    predecessor_info = {
        "merkle_root": final_merkle_root,
        "final_event_count": len(all_events),
        "seal_event_id": seal_event.get("event_id"),
        "seal_event_hash": canonical_hash(seal_event)
    }

    # 2. Bootstrap new vault
    from .cli import _load_keys
    keys_data = _load_keys(keyfile_path)
    
    result = bootstrap_backpack(
        successor_path,
        actor="sovereign_genesis",
        quiet=True
    )
    
    if not result.success:
        raise RuntimeError(f"Failed to bootstrap successor vault: {result.errors}")

    # 3. Inject predecessor pointer into GENESIS event and file
    genesis_path = successor_path / "identity" / "genesis.json"
    genesis_data = json.loads(genesis_path.read_text(encoding="utf-8"))
    genesis_data["predecessor_vault"] = predecessor_info
    genesis_path.write_text(json.dumps(genesis_data, indent=2), encoding="utf-8")

    # Update the GENESIS event in the log too
    events_file_new = successor_path / "events" / "events.ndjson"
    new_events = load_events(events_file_new)
    
    # The first event is GENESIS
    new_events[0]["payload"]["predecessor_vault"] = predecessor_info
    
    # Re-calculate event_id and signature for genesis
    gen_event = new_events[0]
    gen_event.pop("sig", None)
    gen_event.pop("event_id", None)
    eid_hash = canonical_hash(gen_event)
    gen_event["event_id"] = f"evt_{eid_hash[:24]}"
    
    kid = list(keys_data.keys())[0]
    priv = load_private_key_b64(keys_data[kid])
    new_events[0] = sign_event(gen_event, priv, kid)
    
    # Rewrite events.ndjson
    from .sync_v0 import write_events
    write_events(events_file_new, new_events)
    
    # Regenerate manifest
    from .cli import cmd_manifest
    import argparse
    cmd_manifest(argparse.Namespace(path=str(successor_path)))

    return successor_path

def verify_vault_chain(vault_path: Path, vault_registry: Dict[str, Path] | None = None) -> List[Dict[str, Any]]:
    """Verify a chain of rotated vaults."""
    results: List[Dict[str, Any]] = []
    current_path: Path | None = vault_path

    while current_path:
        report: Dict[str, Any] = {"path": str(current_path), "status": "PASS", "errors": []}
        
        # 1. Structural/Integrity check
        try:
            validate_vault_structure(current_path)
        except Exception as e:
            report["status"] = "FAIL"
            report["errors"].append(f"Structure invalid: {e}")

        # 2. Check for predecessor
        genesis_path = current_path / "identity" / "genesis.json"
        if not genesis_path.exists():
            report["status"] = "FAIL"
            report["errors"].append("Genesis file missing")
            results.append(report)
            break
            
        genesis_data = json.loads(genesis_path.read_text(encoding="utf-8"))
        predecessor_info = genesis_data.get("predecessor_vault")
        
        results.append(report)
        
        if predecessor_info:
            # We need to find the predecessor vault
            pred_merkle = predecessor_info["merkle_root"]
            next_path = None
            if vault_registry and pred_merkle in vault_registry:
                next_path = vault_registry[pred_merkle]
            
            if not next_path:
                break
            
            # Verify predecessor matches the pointer
            pred_merkle_actual_path = next_path / "merkle_root.txt"
            if not pred_merkle_actual_path.exists():
                report["status"] = "FAIL"
                report["errors"].append(f"Predecessor {next_path} is missing merkle_root.txt")
                break
                
            pred_merkle_actual = pred_merkle_actual_path.read_text(encoding="utf-8").strip()
            if pred_merkle_actual != pred_merkle:
                report["status"] = "FAIL"
                report["errors"].append(f"Predecessor Merkle root mismatch. Expected {pred_merkle}, got {pred_merkle_actual}")
                break
            
            current_path = next_path
        else:
            current_path = None
            
    return results
