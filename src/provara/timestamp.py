"""
timestamp.py — RFC 3161 Trusted Timestamping for Provara

Allows anchoring vault state hashes to an external Trust Anchor (TSA)
for legal admissibility and independent temporal proof.
"""

import base64
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .backpack_signing import load_private_key_b64, sign_event
from .canonical_json import canonical_dumps, canonical_hash
from .sync_v0 import load_events
from .reducer_v0 import SovereignReducerV0

# Default TSA: FreeTSA.org
DEFAULT_TSA_URL = "https://freetsa.org/tsr"

def get_rfc3161_timestamp(data_hash_hex: str, tsa_url: str = DEFAULT_TSA_URL) -> bytes:
    """Request an RFC 3161 timestamp response (TSR) for a SHA-256 digest.

    Args:
        data_hash_hex: SHA-256 digest in lowercase or uppercase hex.
        tsa_url: RFC 3161 timestamp authority endpoint URL.

    Returns:
        bytes: Raw TSR bytes returned by the timestamp authority.

    Raises:
        RuntimeError: If TSA responds with a non-200 HTTP status.
        ValueError: If ``data_hash_hex`` is invalid hex.
        urllib.error.URLError: If request/connection fails.

    Example:
        tsr = get_rfc3161_timestamp("ab" * 32)
    """
    # RFC 3161 TimeStampReq (simplified binary structure for SHA-256)
    # This is a minimal DER-encoded request. 
    # In production, a full ASN.1 library would be used, but for leverage 
    # we use a template for SHA-256.
    
    hash_bytes = bytes.fromhex(data_hash_hex)
    
    # ASN.1 template for SHA-256 TimeStampReq
    # prefix includes version, messageImprint (sha256 OID), etc.
    req_prefix = bytes.fromhex("303b0201013031300d060960864801650304020105000420")
    req_suffix = bytes.fromhex("02010101") # certReq=true
    
    ts_req = req_prefix + hash_bytes + req_suffix
    
    headers = {"Content-Type": "application/timestamp-query"}
    req = urllib.request.Request(tsa_url, data=ts_req, headers=headers)
    
    with urllib.request.urlopen(req, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"TSA returned status {response.status}")
        content = response.read()
        if not isinstance(content, bytes):
            raise TypeError("Expected bytes from TSA response")
        return content

def record_timestamp_anchor(
    vault_path: Path,
    keyfile_path: Path,
    tsa_url: str = DEFAULT_TSA_URL,
    actor: str = "timestamp_authority",
) -> Dict[str, Any]:
    """Anchor current reducer state hash to an external timestamp authority.

    Args:
        vault_path: Target vault directory.
        keyfile_path: Path to private key file used for event signing.
        tsa_url: RFC 3161 authority endpoint URL.
        actor: Actor label for the timestamp event.

    Returns:
        Dict[str, Any]: Signed timestamp anchor event appended to the vault.

    Raises:
        FileNotFoundError: If required vault files are missing.
        KeyError: If reducer metadata does not include ``state_hash``.
        OSError: If vault files cannot be read or written.

    Example:
        event = record_timestamp_anchor(Path("My_Backpack"), Path("keys.json"))
    """
    # 1. Compute current state hash
    events_file = vault_path / "events" / "events.ndjson"
    all_events = load_events(events_file)
    
    reducer = SovereignReducerV0()
    reducer.apply_events(all_events)
    state = reducer.export_state()
    state_hash = state["metadata"]["state_hash"]
    
    print(f"Anchoring state hash: {state_hash}")
    
    # 2. Get RFC 3161 timestamp
    tsr_bytes = get_rfc3161_timestamp(state_hash, tsa_url)
    tsr_b64 = base64.b64encode(tsr_bytes).decode("ascii")
    
    # 3. Load keys
    with keyfile_path.open("r") as f:
        keys_data = json.load(f)
    
    kid = list(keys_data.keys())[0]
    priv = load_private_key_b64(keys_data[kid])
    
    # 4. Find prev_hash for this actor
    actor_events = [e for e in all_events if e.get("actor") == actor]
    prev_hash = actor_events[-1].get("event_id") if actor_events else None
    
    # 5. Build event (com.provara.timestamp_anchor)
    event = {
        "type": "com.provara.timestamp_anchor",
        "actor": actor,
        "prev_event_hash": prev_hash,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "subject": "vault/state",
            "predicate": "anchored_to_tsa",
            "target_state_hash": state_hash,
            "tsa_url": tsa_url,
            "rfc3161_tsr_b64": tsr_b64,
            "confidence": 1.0
        }
    }
    
    # 6. ID and Sign
    eid_hash = canonical_hash(event)
    event["event_id"] = f"evt_{eid_hash[:24]}"
    signed = sign_event(event, priv, kid)
    
    # 7. Append
    with events_file.open("a", encoding="utf-8") as f:
        f.write(canonical_dumps(signed) + "\n")
        
    return signed
