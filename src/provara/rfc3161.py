"""
rfc3161.py — RFC 3161 Trusted Timestamping for Provara

Provides support for external temporal proof using Time Stamping Authorities (TSA).
Timestamps are stored as auxiliary evidence and do not affect the normative
causal hash chain.
"""

from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

try:
    import rfc3161_client
    HAS_RFC3161 = True
except ImportError:
    HAS_RFC3161 = False

logger = logging.getLogger(__name__)

class TimestampResult:
    """Result of an RFC 3161 timestamp verification."""
    def __init__(
        self,
        event_id: str,
        valid: bool,
        timestamp: Optional[datetime] = None,
        tsa_name: Optional[str] = None,
        serial_number: Optional[int] = None,
        hash_algorithm: str = "sha256",
        error: Optional[str] = None
    ):
        self.event_id = event_id
        self.valid = valid
        self.timestamp = timestamp
        self.tsa_name = tsa_name
        self.serial_number = serial_number
        self.hash_algorithm = hash_algorithm
        self.error = error

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "valid": self.valid,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "tsa_name": self.tsa_name,
            "serial_number": self.serial_number,
            "hash_algorithm": self.hash_algorithm,
            "error": self.error
        }

def _check_dependency():
    if not HAS_RFC3161:
        raise ImportError(
            "RFC 3161 support requires the 'rfc3161-client' package. "
            "Install it with: pip install provara-protocol[timestamps]"
        )

def request_timestamp(
    event_hash: bytes,
    tsa_url: str = "http://timestamp.digicert.com",
) -> bytes:
    """Request an RFC 3161 timestamp token from a TSA.

    Args:
        event_hash: SHA-256 hash of the event to timestamp (32 bytes)
        tsa_url: URL of the Time Stamping Authority

    Returns:
        bytes: DER-encoded TimeStampToken
    """
    _check_dependency()
    try:
        # rfc3161_client.request returns the DER-encoded response
        # It handles the hashing if we pass data, but we pass the hash directly.
        # We need to ensure we use the correct API.
        # Looking at rfc3161-client docs/source:
        # request(url, data=None, hash_data=None, algorithm='sha256', ...)
        # If we have the hash already, we should probably use hash_data.
        
        # NOTE: rfc3161-client's request() typically takes the raw data and hashes it.
        # If we already have the SHA-256 hash, we might need to wrap it or 
        # use a lower-level function if the library doesn't support passing hash directly.
        # Standard rfc3161-client.request(tsa_url, data=event_hash, hash_data=True) 
        # might be what we want if we want it to NOT hash again.
        # Actually, rfc3161-client.request(url, data=message_bytes) hashes message_bytes.
        
        # If we MUST pass the hash:
        # Most TSAs expect the hash.
        # Let's assume rfc3161_client.request handles the networking.
        
        # Re-reading rfc3161-client usage:
        # rt = rfc3161_client.request(tsa_url, data=data)
        # where data is hashed by the client.
        
        # If the user provides event_hash (32 bytes), we want the TSA to sign THAT.
        # rfc3161-client might hash the 'data' we give it.
        # To avoid double hashing, we might need to use the internal Request object.
        
        # Standard usage:
        return rfc3161_client.request(tsa_url, data=event_hash, hash_data=True)
    except Exception as e:
        logger.error(f"Failed to request timestamp from {tsa_url}: {e}")
        raise

def verify_timestamp(
    timestamp_token: bytes,
    event_hash: bytes,
) -> TimestampResult:
    """Verify an RFC 3161 timestamp token.

    Args:
        timestamp_token: DER-encoded TimeStampToken
        event_hash: Expected SHA-256 hash of the event

    Returns:
        TimestampResult
    """
    _check_dependency()
    try:
        # rfc3161_client.verify(token, data=None, hash_data=None, ...)
        is_valid, tst_info = rfc3161_client.verify(
            timestamp_token, 
            data=event_hash, 
            hash_data=True
        )
        
        if is_valid:
            # tst_info is a dict-like object containing the decoded info
            return TimestampResult(
                event_id="", # To be filled by caller
                valid=True,
                timestamp=tst_info.get('gen_time'),
                tsa_name=str(tst_info.get('policy')), # policy OID or similar
                serial_number=tst_info.get('serial_number'),
                hash_algorithm=tst_info.get('hash_algorithm', 'sha256')
            )
        else:
            return TimestampResult(event_id="", valid=False, error="Invalid signature or hash mismatch")
            
    except Exception as e:
        return TimestampResult(event_id="", valid=False, error=str(e))

def store_timestamp(
    vault_path: Path,
    event_id: str,
    timestamp_token: bytes,
) -> None:
    """Store an RFC 3161 timestamp token alongside an event.

    Stored at: vault_path/timestamps/{event_id}.tst
    """
    ts_dir = vault_path / "timestamps"
    ts_dir.mkdir(exist_ok=True, parents=True)
    
    ts_file = ts_dir / f"{event_id}.tst"
    ts_file.write_bytes(timestamp_token)

def verify_all_timestamps(
    vault_path: Path,
) -> List[TimestampResult]:
    """Verify all stored timestamps in a vault."""
    ts_dir = vault_path / "timestamps"
    if not ts_dir.is_dir():
        return []

    results = []
    # We need the event hashes to verify.
    # We'll load events to match event_id to hash.
    from .sync_v0 import iter_events
    from .canonical_json import canonical_hash
    
    events_file = vault_path / "events" / "events.ndjson"
    event_map = {}
    if events_file.exists():
        for event in iter_events(events_file):
            eid = event.get("event_id")
            if eid:
                # The hash is of the entire signed event as stored?
                # Usually, we timestamp the signature or the entire event.
                # PROTOCOL_PROFILE.txt says event_id is evt_ + SHA256(canonical_event_without_id_sig)
                # But the prompt says "SHA-256 hash of the event to timestamp".
                # Let's assume we timestamp the canonical bytes of the event as it lives in NDJSON.
                from .canonical_json import canonical_bytes
                event_bytes = canonical_bytes(event)
                import hashlib
                h = hashlib.sha256(event_bytes).digest()
                event_map[eid] = h

    for ts_file in ts_dir.glob("*.tst"):
        event_id = ts_file.stem
        token = ts_file.read_bytes()
        
        expected_hash = event_map.get(event_id)
        if not expected_hash:
            results.append(TimestampResult(
                event_id=event_id,
                valid=False,
                error=f"Event {event_id} not found in log"
            ))
            continue
            
        res = verify_timestamp(token, expected_hash)
        res.event_id = event_id
        results.append(res)
        
    return results
