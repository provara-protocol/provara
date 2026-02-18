"""
redaction.py — Redaction Implementation for Provara Protocol

Implements Task 1: Redaction Event Type and Tombstone Pattern.
"""

from __future__ import annotations
import json
import datetime
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .canonical_json import canonical_hash, canonical_dumps
from .backpack_signing import load_private_key_b64, sign_event
from .sync_v0 import load_events, write_events
from .manifest_generator import build_manifest, manifest_leaves
from .backpack_integrity import merkle_root_hex, MANIFEST_EXCLUDE, canonical_json_bytes

def _load_keys_internal(keys_path: Path) -> Dict[str, str]:
    """Internal helper to load keys without importing from cli.py."""
    if not keys_path.exists():
        raise FileNotFoundError(f"Private keys file not found at {keys_path}")
    data = json.loads(keys_path.read_text())
    
    if "keys" in data and isinstance(data["keys"], list):
        return {str(k["key_id"]): str(k["private_key_b64"]) for k in data["keys"]}
    else:
        return {str(k): str(v) for k, v in data.items() if k != "WARNING"}

def redact_event(
    vault_path: Path,
    keyfile_path: Path,
    target_event_id: str,
    reason: str,
    authority: str,
    reason_detail: Optional[str] = None,
    redaction_method: str = "TOMBSTONE",
    actor: Optional[str] = None,
    key_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Redact an event by replacing its content with a tombstone and 
    appending a com.provara.redaction event.
    """
    events_path = vault_path / "events" / "events.ndjson"
    if not events_path.exists():
        raise FileNotFoundError(f"Events log not found at {events_path}")
        
    all_events = load_events(events_path)
    
    target_event = None
    target_index = -1
    for i, e in enumerate(all_events):
        if e.get("event_id") == target_event_id:
            target_event = e
            target_index = i
            break
            
    if target_event is None:
        raise ValueError(f"Target event {target_event_id} not found")
        
    if target_event.get("payload", {}).get("redacted") is True:
        # Idempotent: if already redacted, find the redaction event and return it
        redaction_event_id = target_event.get("payload", {}).get("redaction_event_id")
        for e in all_events:
            if e.get("event_id") == redaction_event_id:
                return e
        return target_event 

    # 1. Load keys
    keys_data = _load_keys_internal(keyfile_path)
    kid = key_id or list(keys_data.keys())[0]
    priv = load_private_key_b64(keys_data[kid])
    
    # 2. Create com.provara.redaction event
    # Find prev_hash for redaction actor
    actor_name = actor or "provara_redactor"
    actor_events = [e for e in all_events if e.get("actor") == actor_name]
    prev_hash = actor_events[-1].get("event_id") if actor_events else None
    
    redaction_payload = {
        "target_event_id": target_event_id,
        "reason": reason,
        "reason_detail": reason_detail,
        "redaction_method": redaction_method,
        "authority": authority
    }
    
    redaction_event = {
        "type": "com.provara.redaction",
        "actor": actor_name,
        "prev_event_hash": prev_hash,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "payload": redaction_payload
    }
    
    # ts_logical handling if it exists in previous events
    if actor_events:
        redaction_event["ts_logical"] = actor_events[-1].get("ts_logical", 0) + 1
    else:
        # Check if any event has ts_logical to maintain consistency
        any_ts_logical = any("ts_logical" in e for e in all_events)
        if any_ts_logical:
            redaction_event["ts_logical"] = 1

    eid_hash = canonical_hash(redaction_event)
    redaction_event["event_id"] = f"evt_{eid_hash[:24]}"
    signed_redaction = sign_event(redaction_event, priv, kid)
    
    # 3. Create Tombstone
    original_payload = target_event.get("payload", {})
    original_payload_hash = canonical_hash(original_payload)
    
    tombstone_payload = {
        "redacted": True,
        "redaction_event_id": signed_redaction["event_id"],
        "original_payload_hash": original_payload_hash,
        "redaction_reason": reason
    }
    
    # Modify target event in place (keeping event_id and sig)
    # We create a new dict to avoid side effects if needed, but here we replace in list
    new_target = dict(target_event)
    new_target["payload"] = tombstone_payload
    all_events[target_index] = new_target
    
    # 4. Append redaction event
    all_events.append(signed_redaction)
    
    # 5. Write back
    write_events(events_path, all_events)
    
    # 6. Regenerate manifest
    exclude = set(MANIFEST_EXCLUDE)
    manifest = build_manifest(vault_path, exclude)
    leaves = manifest_leaves(manifest)
    root_hex = merkle_root_hex(leaves)
    
    (vault_path / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    (vault_path / "merkle_root.txt").write_text(root_hex + "\n", encoding="utf-8")
    
    return signed_redaction
