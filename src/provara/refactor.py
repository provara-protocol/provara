"""
refactor.py — Provara Vault Refactoring & Consolidation Tools
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from .canonical_json import canonical_hash, canonical_dumps
from .backpack_signing import sign_event, load_private_key_b64
from .sync_v0 import load_events, write_events
from .manifest_generator import build_manifest, manifest_leaves
from .backpack_integrity import MANIFEST_EXCLUDE, canonical_json_bytes, merkle_root_hex

def normalize_identities(
    vault_path: Path,
    identity_map: Dict[str, str],
    private_key_b64: str,
    key_id: str
) -> int:
    events_file = vault_path / "events" / "events.ndjson"
    events = load_events(events_file)
    private_key = load_private_key_b64(private_key_b64)
    
    new_events = []
    # Initialize with mapping for None (root)
    # We also keep existing IDs unchanged until they are refactored
    old_to_new_hash = {None: None}
    
    for event in events:
        old_id = event.get("event_id")
        
        # 1. Apply actor mapping
        old_actor = event.get("actor")
        if old_actor in identity_map:
            event["actor"] = identity_map[old_actor]
            
        # 2. Update causal chain
        old_prev = event.get("prev_event_hash")
        # If we have a new hash for the previous event, use it.
        # Otherwise, keep the old one (it might be a cross-project ref we haven't touched yet)
        if old_prev in old_to_new_hash:
            event["prev_event_hash"] = old_to_new_hash[old_prev]
        
        # 3. Strip old identity metadata
        event.pop("event_id", None)
        event.pop("sig", None)
        event.pop("actor_key_id", None)
        
        # 4. Generate NEW event_id from refactored unsigned content
        new_eid_hash = canonical_hash(event)
        new_id = f"evt_{new_eid_hash[:24]}"
        event["event_id"] = new_id
        
        # 5. Sign the event (includes actor_key_id and sig)
        signed_event = sign_event(event, private_key, key_id)
        
        # 6. Map old ID to new ID for next event's prev_hash
        old_to_new_hash[old_id] = new_id
        new_events.append(signed_event)
        
    # Write back and regenerate manifest
    write_events(events_file, new_events)
    _regenerate_vault_metadata(vault_path)
    
    return len(new_events)

def _regenerate_vault_metadata(vault_path: Path):
    manifest = build_manifest(vault_path, set(MANIFEST_EXCLUDE))
    leaves = manifest_leaves(manifest)
    root_hex = merkle_root_hex(leaves)
    (vault_path / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    (vault_path / "merkle_root.txt").write_text(root_hex + "\n", encoding="utf-8")

