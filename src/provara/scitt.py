"""
scitt.py — SCITT Phase 1 compatibility for Provara

Adds two event types that bridge Provara vaults to the IETF SCITT architecture:

  com.ietf.scitt.signed_statement — wraps a SCITT Signed Statement as a
      Provara event, storing the statement hash, content type, subject, issuer,
      and (optionally) a Base64-encoded COSE Sign1 envelope.

  com.ietf.scitt.receipt — wraps a SCITT Receipt as a Provara event,
      referencing the originating signed_statement event and embedding the
      transparency service's inclusion proof.

Both types are OPTIONAL — core vault operations are not affected.
No new dependencies are introduced; all serialization uses stdlib.

Reference: https://datatracker.ietf.org/wg/scitt/about/
Mapping:   docs/SCITT_MAPPING.md
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .backpack_signing import load_private_key_b64, sign_event
from .canonical_json import canonical_dumps, canonical_hash
from .sync_v0 import load_events

# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

SIGNED_STATEMENT_TYPE = "com.ietf.scitt.signed_statement"
RECEIPT_TYPE = "com.ietf.scitt.receipt"


# ---------------------------------------------------------------------------
# Schema validation (no new deps — lightweight inline checks)
# ---------------------------------------------------------------------------

def _validate_statement_payload(payload: Dict[str, Any]) -> None:
    """Raise ValueError if required fields are missing or malformed."""
    required = ("statement_hash", "content_type", "subject", "issuer")
    for field in required:
        if not payload.get(field):
            raise ValueError(f"SCITT signed_statement requires non-empty '{field}'")
    h = payload["statement_hash"]
    if len(h) != 64 or not all(c in "0123456789abcdefABCDEF" for c in h):
        raise ValueError(
            f"statement_hash must be a 64-character SHA-256 hex string, got: {h!r}"
        )


def _validate_receipt_payload(payload: Dict[str, Any]) -> None:
    """Raise ValueError if required fields are missing or malformed."""
    required = ("statement_event_id", "transparency_service", "inclusion_proof")
    for field in required:
        if not payload.get(field):
            raise ValueError(f"SCITT receipt requires non-empty '{field}'")
    sid = payload["statement_event_id"]
    if not isinstance(sid, str) or not sid.startswith("evt_"):
        raise ValueError(
            f"statement_event_id must be a Provara event ID (evt_...), got: {sid!r}"
        )


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def record_scitt_statement(
    vault_path: Path,
    keyfile_path: Path,
    statement_hash: str,
    content_type: str,
    subject: str,
    issuer: str,
    cose_envelope_b64: Optional[str] = None,
    actor: str = "scitt_agent",
) -> Dict[str, Any]:
    """
    Append a com.ietf.scitt.signed_statement event to the vault.

    Args:
        vault_path:        Path to the Provara vault directory.
        keyfile_path:      Path to the private keys JSON file.
        statement_hash:    SHA-256 hex digest of the original SCITT statement.
        content_type:      MIME type of the statement (e.g. 'application/json').
        subject:           What the statement is about.
        issuer:            Who made the statement (DID, key ID, or free string).
        cose_envelope_b64: Optional Base64-encoded COSE Sign1 envelope.
        actor:             Provara actor label for this event.

    Returns:
        The signed event dict (already appended to events.ndjson).
    """
    payload: Dict[str, Any] = {
        "statement_hash": statement_hash,
        "content_type": content_type,
        "subject": subject,
        "issuer": issuer,
    }
    if cose_envelope_b64 is not None:
        payload["cose_envelope_b64"] = cose_envelope_b64
    _validate_statement_payload(payload)
    return _append_scitt_event(vault_path, keyfile_path, SIGNED_STATEMENT_TYPE, payload, actor)


def record_scitt_receipt(
    vault_path: Path,
    keyfile_path: Path,
    statement_event_id: str,
    transparency_service: str,
    inclusion_proof: Any,
    receipt_b64: Optional[str] = None,
    actor: str = "scitt_agent",
) -> Dict[str, Any]:
    """
    Append a com.ietf.scitt.receipt event to the vault.

    Args:
        vault_path:           Path to the Provara vault directory.
        keyfile_path:         Path to the private keys JSON file.
        statement_event_id:   event_id of the signed_statement event (evt_...).
        transparency_service: URL or identifier of the transparency service.
        inclusion_proof:      Proof data from the TS (string, dict, or list).
        receipt_b64:          Optional Base64-encoded CBOR receipt.
        actor:                Provara actor label for this event.

    Returns:
        The signed event dict (already appended to events.ndjson).
    """
    payload: Dict[str, Any] = {
        "statement_event_id": statement_event_id,
        "transparency_service": transparency_service,
        "inclusion_proof": inclusion_proof,
    }
    if receipt_b64 is not None:
        payload["receipt_b64"] = receipt_b64
    _validate_receipt_payload(payload)
    return _append_scitt_event(vault_path, keyfile_path, RECEIPT_TYPE, payload, actor)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_key_from_file(keyfile_path: Path):
    """
    Returns (kid, Ed25519PrivateKey). Handles both keyfile formats:
      - {keys: [{key_id, private_key_b64, ...}, ...]}  (from provara init)
      - {kid: b64_str, ...}                             (legacy flat format)
    """
    data = json.loads(keyfile_path.read_text())
    if "keys" in data and isinstance(data["keys"], list):
        entry = data["keys"][0]
        return entry["key_id"], load_private_key_b64(entry["private_key_b64"])
    # Flat format
    kid = next(k for k in data if k != "WARNING")
    return kid, load_private_key_b64(data[kid])


def _append_scitt_event(
    vault_path: Path,
    keyfile_path: Path,
    event_type: str,
    payload: Dict[str, Any],
    actor: str,
) -> Dict[str, Any]:
    """Build, sign, and append a SCITT event. Returns the signed event."""
    events_file = vault_path / "events" / "events.ndjson"

    kid, priv = _load_key_from_file(keyfile_path)

    # Find prev_hash for this actor
    all_events = load_events(events_file)
    actor_events = [e for e in all_events if e.get("actor") == actor]
    prev_hash = actor_events[-1].get("event_id") if actor_events else None

    event = {
        "type": event_type,
        "actor": actor,
        "prev_event_hash": prev_hash,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }

    # Content-addressed ID
    eid_hash = canonical_hash(event)
    event["event_id"] = f"evt_{eid_hash[:24]}"

    signed = sign_event(event, priv, kid)

    with events_file.open("a", encoding="utf-8") as f:
        f.write(canonical_dumps(signed) + "\n")

    return signed
