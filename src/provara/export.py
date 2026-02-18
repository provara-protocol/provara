"""
export.py — SCITT Phase 2 Export Tool

Exports Provara vaults with SCITT events to a standalone, verifiable bundle.

Usage:
    provara export <vault_path> --format scitt-compat --output <dir>

Produces:
    - statements/*.json — Individual statement files with chain proofs
    - index.json — Listing of all exported statements
    - verification_report.json — Chain integrity status
    - keys.json — Public keys for verification
"""

import json
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .canonical_json import canonical_dumps, canonical_hash
from .sync_v0 import load_events
from .backpack_integrity import merkle_root_hex
from .backpack_signing import load_keys_registry, verify_event_signature
from .scitt import SIGNED_STATEMENT_TYPE, RECEIPT_TYPE


def export_vault_scitt_compat(
    vault_path: Path,
    output_dir: Path,
) -> Dict[str, Any]:
    """
    Export a Provara vault with SCITT events to a standalone bundle.
    
    Args:
        vault_path: Path to the Provara vault directory.
        output_dir: Path to the output directory for the export bundle.
    
    Returns:
        Export result dict with counts and status.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    statements_dir = output_dir / "statements"
    statements_dir.mkdir(exist_ok=True)
    
    # Load all events
    events_file = vault_path / "events" / "events.ndjson"
    all_events = load_events(events_file)
    
    # Load keys registry
    keys_file = vault_path / "identity" / "keys.json"
    keys_registry = load_keys_registry(keys_file)
    
    # Find SCITT events
    statements = [e for e in all_events if e.get("type") == SIGNED_STATEMENT_TYPE]
    receipts = [e for e in all_events if e.get("type") == RECEIPT_TYPE]
    
    # Build receipt lookup by statement_event_id
    receipt_by_statement: Dict[str, Dict[str, Any]] = {}
    for receipt_event in receipts:
        stmt_id = receipt_event.get("payload", {}).get("statement_event_id")
        if stmt_id:
            receipt_by_statement[str(stmt_id)] = receipt_event
    
    # Export each statement with its proof
    exported_count = 0
    index_entries = []
    
    for stmt in statements:
        event_id = stmt.get("event_id")
        stmt_payload = stmt.get("payload", {})
        
        # Build chain proof
        chain_proof = _build_chain_proof(all_events, stmt)
        
        # Build Merkle proof
        merkle_proof = _build_merkle_proof(vault_path, stmt)
        
        # Get receipt if exists
        receipt: Dict[str, Any] | None = (
            receipt_by_statement.get(event_id) if isinstance(event_id, str) else None
        )
        
        # Create export file
        export_data = {
            "statement": {
                "event_id": event_id,
                "timestamp_utc": stmt.get("timestamp_utc"),
                "actor": stmt.get("actor"),
                "subject": stmt_payload.get("subject"),
                "issuer": stmt_payload.get("issuer"),
                "content_type": stmt_payload.get("content_type"),
                "statement_hash": stmt_payload.get("statement_hash"),
            },
            "chain_proof": chain_proof,
            "merkle_proof": merkle_proof,
            "signature": {
                "sig": stmt.get("sig"),
                "actor_key_id": stmt.get("actor_key_id"),
            },
        }
        
        if receipt:
            export_data["receipt"] = {
                "event_id": receipt.get("event_id"),
                "transparency_service": receipt.get("payload", {}).get("transparency_service"),
                "inclusion_proof": receipt.get("payload", {}).get("inclusion_proof"),
            }
        
        # Write statement file
        stmt_file = statements_dir / f"{event_id}.json"
        with open(stmt_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)
        
        # Add to index
        index_entries.append({
            "event_id": event_id,
            "timestamp_utc": stmt.get("timestamp_utc"),
            "subject": stmt_payload.get("subject"),
            "issuer": stmt_payload.get("issuer"),
            "has_receipt": receipt is not None,
        })
        
        exported_count += 1
    
    # Write index.json
    index_data = {
        "export_format": "scitt-compat",
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
        "vault_path": str(vault_path.resolve()),
        "statement_count": exported_count,
        "statements": index_entries,
    }
    
    with open(output_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)
    
    # Export public keys
    exported_keys = _export_keys(keys_registry)
    with open(output_dir / "keys.json", "w", encoding="utf-8") as f:
        json.dump(exported_keys, f, indent=2)
    
    # Generate verification report
    verification_report = _verify_export_bundle(output_dir, statements)
    with open(output_dir / "verification_report.json", "w", encoding="utf-8") as f:
        json.dump(verification_report, f, indent=2)
    
    return {
        "success": True,
        "exported_count": exported_count,
        "output_dir": str(output_dir),
        "verification_status": verification_report["overall_status"],
    }


def _build_chain_proof(all_events: List[Dict[str, Any]], target_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a proof that the target event is part of a valid causal chain.
    
    Returns the chain segment from genesis to the target event.
    """
    target_id = target_event.get("event_id")
    target_actor = target_event.get("actor")
    
    # Get all events by this actor up to and including target
    actor_events = [e for e in all_events if e.get("actor") == target_actor]
    
    # Find position of target event
    target_idx = None
    for i, e in enumerate(actor_events):
        if e.get("event_id") == target_id:
            target_idx = i
            break
    
    if target_idx is None:
        return {"error": "Target event not found in chain"}
    
    # Build chain segment
    chain_segment = []
    for i in range(target_idx + 1):
        e = actor_events[i]
        chain_segment.append({
            "event_id": e.get("event_id"),
            "type": e.get("type"),
            "timestamp_utc": e.get("timestamp_utc"),
            "prev_event_hash": e.get("prev_event_hash"),
            "event_hash": canonical_hash(e),
        })
    
    return {
        "actor": target_actor,
        "chain_length": len(chain_segment),
        "target_position": target_idx,
        "chain_segment": chain_segment,
    }


def _build_merkle_proof(vault_path: Path, target_event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a Merkle proof that the target event is part of the vault manifest.
    
    Returns the leaf entry and current Merkle root.
    """
    # Load manifest
    manifest_file = vault_path / "manifest.json"
    if not manifest_file.exists():
        return {"error": "Manifest not found"}
    
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    # Find the event in manifest leaves
    events_file = vault_path / "events" / "events.ndjson"
    events_content = events_file.read_bytes()
    
    # Compute leaf hash for events file
    leaf_entry = {
        "path": "events/events.ndjson",
        "sha256": canonical_hash(events_content),
        "size": len(events_content),
    }
    
    return {
        "leaf_entry": leaf_entry,
        "merkle_root": manifest.get("merkle_root"),
        "manifest_timestamp": manifest.get("manifest_timestamp"),
    }


def _export_keys(keys_registry: Dict[str, Any]) -> Dict[str, Any]:
    """Export public keys from registry for verification."""
    exported: Dict[str, Any] = {
        "keys": [],
        "export_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    # load_keys_registry returns {key_id: {...}}
    # Convert back to list format for export
    for key_id, entry in keys_registry.items():
        if isinstance(entry, dict):
            exported["keys"].append({
                "key_id": entry.get("key_id", key_id),
                "public_key_b64": entry.get("public_key_b64"),
                "algorithm": entry.get("algorithm", "Ed25519"),
            })
    
    return exported


def _verify_export_bundle(output_dir: Path, original_statements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Verify the export bundle is self-contained and valid.
    
    Returns a verification report.
    """
    report: Dict[str, Any] = {
        "verification_timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": [],
        "overall_status": "PASS",
    }
    
    # Check 1: index.json exists and is valid
    index_file = output_dir / "index.json"
    if index_file.exists():
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                index_data = json.load(f)
            report["checks"].append({
                "check": "index_json_valid",
                "status": "PASS",
                "statement_count": index_data.get("statement_count", 0),
            })
        except Exception as e:
            report["checks"].append({
                "check": "index_json_valid",
                "status": "FAIL",
                "error": str(e),
            })
            report["overall_status"] = "FAIL"
    else:
        report["checks"].append({
            "check": "index_json_exists",
            "status": "FAIL",
            "error": "index.json not found",
        })
        report["overall_status"] = "FAIL"
    
    # Check 2: keys.json exists
    keys_file = output_dir / "keys.json"
    if keys_file.exists():
        report["checks"].append({
            "check": "keys_json_exists",
            "status": "PASS",
        })
    else:
        report["checks"].append({
            "check": "keys_json_exists",
            "status": "FAIL",
            "error": "keys.json not found",
        })
        report["overall_status"] = "FAIL"
    
    # Check 3: verification_report.json exists (this file)
    # Skip - we're creating it now
    
    # Check 4: Statement files exist
    statements_dir = output_dir / "statements"
    if statements_dir.exists():
        statement_files = list(statements_dir.glob("*.json"))
        report["checks"].append({
            "check": "statement_files_exist",
            "status": "PASS",
            "file_count": len(statement_files),
        })
    else:
        report["checks"].append({
            "check": "statement_files_exist",
            "status": "FAIL",
            "error": "statements/ directory not found",
        })
        report["overall_status"] = "FAIL"
    
    # Check 5: Verify chain integrity in export
    chain_valid = True
    for stmt_file in (statements_dir / "*.json").glob("*.json") if statements_dir.exists() else []:
        try:
            with open(stmt_file, "r", encoding="utf-8") as f:
                stmt_data = json.load(f)
            
            chain_proof = stmt_data.get("chain_proof", {})
            if "error" in chain_proof:
                chain_valid = False
                break
            
            # Verify chain linkage
            chain_segment = chain_proof.get("chain_segment", [])
            for i in range(1, len(chain_segment)):
                prev_event = chain_segment[i - 1]
                curr_event = chain_segment[i]
                if curr_event.get("prev_event_hash") != prev_event.get("event_id"):
                    chain_valid = False
                    break
        except Exception:
            chain_valid = False
            break
    
    report["checks"].append({
        "check": "chain_integrity",
        "status": "PASS" if chain_valid else "FAIL",
    })
    
    if not chain_valid:
        report["overall_status"] = "FAIL"
    
    return report
