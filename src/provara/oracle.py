"""
oracle.py — Provara Market Oracle Prototype

Closes the loop between predictions and reality.
1. Scans vault for MARKET_ALPHA events.
2. Fetches 'current' market state (mocked for prototype).
3. Records PERFORMANCE_ATTESTATION events linking to the original alpha.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json

from .sync_v0 import load_events
from .market import _append_market_event
from .canonical_json import canonical_hash, canonical_dumps
from .backpack_signing import sign_event, load_private_key_b64

def validate_market_alpha(
    vault_path: Path,
    keyfile: Path,
    actor: str = "oracle_node_01",
) -> List[Dict[str, Any]]:
    """
    Find unvalidated MARKET_ALPHA events and attest to their performance.
    """
    # 0. Check seal
    from .archival import is_vault_sealed
    if is_vault_sealed(vault_path):
        raise RuntimeError(f"Vault at {vault_path} is SEALED.")

    # 1. Load all events
    events_file = vault_path / "events" / "events.ndjson"
    all_events = load_events(events_file)
    
    # 2. Identify MARKET_ALPHA events
    # We look for events with payload.extension == "provara.market.market_alpha"
    alpha_events = [
        e for e in all_events 
        if e.get("payload", {}).get("extension") == "provara.market.market_alpha"
    ]
    
    # 3. Identify existing ATTESTATIONS to avoid duplicates
    attested_ids = {
        e.get("payload", {}).get("target_event_id")
        for e in all_events
        if e.get("type") == "ATTESTATION"
    }
    
    pending = [e for e in alpha_events if e["event_id"] not in attested_ids]
    results = []
    
    if not pending:
        return []

    # 4. Load signing keys for the Oracle
    keys_data = json.loads(keyfile.read_text())
    kid = list(keys_data.keys())[0]
    priv = load_private_key_b64(keys_data[kid])

    for alpha in pending:
        payload = alpha["payload"]
        val = payload["value"]
        ticker = val["ticker"]
        signal = val["signal"]
        
        # MOCK REALITY: In a real system, this fetches from Binance/Coinbase API
        # For prototype, we "look into the future" or simulate a 2% gain for LONGs
        simulated_gain = 0.0215 # +2.15%
        is_correct = (signal == "LONG" and simulated_gain > 0) or (signal == "SHORT" and simulated_gain < 0)
        
        attestation_value = {
            "performance_pct": simulated_gain * 100,
            "status": "SUCCESS" if is_correct else "FAIL",
            "observation_window": "interim_prototype",
            "realized_at_utc": datetime.now(timezone.utc).isoformat()
        }
        
        # 5. Build ATTESTATION event (Standard Provara Type)
        # Note: We find the latest event for THIS actor (the Oracle) for the chain link
        actor_events = [e for e in all_events if e.get("actor_key_id") == kid]
        prev_hash = actor_events[-1].get("event_id") if actor_events else None
        
        event = {
            "type": "ATTESTATION",
            "actor": actor,
            "prev_event_hash": prev_hash,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "subject": f"performance:{ticker}",
                "predicate": "evaluation",
                "value": attestation_value,
                "target_event_id": alpha["event_id"],
                "confidence": 1.0,
                "extension": "provara.oracle.performance_v1"
            }
        }
        
        # 6. Sign and Append
        eid_hash = canonical_hash(event)
        event["event_id"] = f"evt_{eid_hash[:24]}"
        signed = sign_event(event, priv, kid)
        
        with open(events_file, "a", encoding="utf-8") as f:
            f.write(canonical_dumps(signed) + "\n")
            
        results.append(signed)
        # Update all_events so the next iteration sees this Oracle event as the latest
        all_events.append(signed)

    return results
