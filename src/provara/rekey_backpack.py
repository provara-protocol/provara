"""
rekey_backpack.py — Backpack v1.0 Key Rotation Protocol

Handles the "Broken Trust" failure mode: revokes a compromised key and
promotes a new one WITHOUT losing the 20-year chain of evidence.

CRITICAL SECURITY MODEL:
  The rotation event MUST be signed by a SURVIVING TRUSTED AUTHORITY,
  never by the new key itself. The new key is the SUBJECT of the rotation,
  not the SIGNER.

  If the new key signed its own promotion, any attacker could generate a
  keypair and self-authorize. The trust chain would be broken.

Authority resolution for signing the rotation:
  1. If a non-compromised root key survives → it signs the rotation.
  2. If root is compromised but quorum keys survive → quorum signs.
  3. If root is compromised and insufficient quorum → fall to degradation
     ladder (archive peer, then human out-of-band re-establishment).
  4. If ALL keys are compromised → catastrophic identity death. Not a
     rotation — requires new genesis with cross-reference to old chain.

Process:
  1. Generate new keypair (offline, never touches the backpack as private).
  2. Append KEY_REVOCATION event (signed by surviving authority) marking
     the compromised key as revoked with a trust boundary event.
  3. Append KEY_PROMOTION event (signed by surviving authority) introducing
     the new public key with roles and scopes.
  4. Update identity/keys.json: mark old key status='revoked', add new key.
  5. Regenerate manifest.json and merkle_root.txt.
  6. Sign new manifest.sig with surviving authority key (or new key if
     the new key has now been attested by the rotation events).

Safety constraints during rotation:
  - L2-L3 actions are BLOCKED until rotation is complete and synced.
  - The system operates under degradation_ladder rules during the window.
  - The rotation itself is L0 (data-only, reversible via counter-rotation).

Dependencies:
  - backpack_signing.py (Ed25519 primitives)
  - canonical_json.py (deterministic serialization)
  - manifest_generator.py (manifest regeneration)
"""

from __future__ import annotations
import copy
import json
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .canonical_json import canonical_bytes, canonical_dumps, canonical_hash
from .backpack_signing import (
    BackpackKeypair,
    key_id_from_public_bytes,
    load_keys_registry,
    load_public_key_b64,
    sign_event,
    sign_manifest,
    verify_event_signature,
    _utc_now_iso,
)


# ---------------------------------------------------------------------------
# Event builders
# ---------------------------------------------------------------------------

def _next_logical_ts(events_path: Path, actor: str) -> int:
    """Find the next ts_logical for a given actor by scanning the event log."""
    max_ts = 0
    if events_path.is_file():
        with events_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    if e.get("actor") == actor:
                        ts = e.get("ts_logical", 0) or 0
                        max_ts = max(max_ts, ts)
                except json.JSONDecodeError:
                    continue
    return max_ts + 1


def _last_event_id_for_actor(events_path: Path, actor: str) -> Optional[str]:
    """Find the last event_id for a given actor (for prev_event_hash)."""
    last_id = None
    if events_path.is_file():
        with events_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    if e.get("actor") == actor:
                        last_id = e.get("event_id")
                except json.JSONDecodeError:
                    continue
    return last_id


def build_rotation_event(
    event_type: str,
    payload: Dict[str, Any],
    actor: str,
    events_path: Path,
) -> Dict[str, Any]:
    """Build an unsigned rotation event with proper chaining."""
    ts_logical = _next_logical_ts(events_path, actor)
    prev_hash = _last_event_id_for_actor(events_path, actor)
    now = _utc_now_iso()

    event = {
        "event_id": None,  # set after content is known
        "type": event_type,
        "namespace": "canonical",
        "actor": actor,
        "ts_logical": ts_logical,
        "prev_event_hash": prev_hash,
        "timestamp_utc": now,
        "payload": payload,
    }

    # Compute content-addressed event_id (hash of event without sig and event_id)
    hashable = {k: v for k, v in event.items() if k not in ("event_id", "sig")}
    event["event_id"] = f"evt_{canonical_hash(hashable)[:24]}"
    return event


def append_event(events_path: Path, event: Dict[str, Any]) -> None:
    """Append a single event to events.ndjson."""
    line = canonical_dumps(event) + "\n"
    with events_path.open("a", encoding="utf-8") as f:
        f.write(line)


# ---------------------------------------------------------------------------
# Core rotation procedure
# ---------------------------------------------------------------------------

class RotationResult:
    """Result of a key rotation operation."""

    def __init__(self) -> None:
        self.success: bool = False
        self.revocation_event_id: Optional[str] = None
        self.promotion_event_id: Optional[str] = None
        self.new_key_id: Optional[str] = None
        self.old_key_id: Optional[str] = None
        self.signed_by: Optional[str] = None
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def __repr__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"RotationResult({status}, "
            f"old={self.old_key_id}, new={self.new_key_id}, "
            f"signed_by={self.signed_by}, "
            f"errors={self.errors})"
        )


def rotate_key(
    backpack_root: Path,
    compromised_key_id: str,
    signing_private_key: Ed25519PrivateKey,
    signing_key_id: str,
    new_keypair: Optional[BackpackKeypair] = None,
    new_key_roles: Optional[List[str]] = None,
    trust_boundary_event_id: Optional[str] = None,
    actor: str = "key_rotation_authority",
) -> RotationResult:
    """
    Perform a complete key rotation.

    Args:
        backpack_root: Path to the backpack directory.
        compromised_key_id: key_id to revoke.
        signing_private_key: Private key of the SURVIVING trusted authority.
        signing_key_id: key_id of the signing authority.
        new_keypair: New keypair to promote. If None, one is generated.
        new_key_roles: Roles for the new key. Defaults to same as revoked key.
        trust_boundary_event_id: Last event_id signed by the compromised key
            that is considered trustworthy. Events after this by the
            compromised key should be quarantined.
        actor: Actor name for the rotation events.

    Returns:
        RotationResult with event IDs, new key ID, and status.

    SECURITY: signing_key_id MUST NOT equal compromised_key_id.
              The compromised key cannot authorize its own replacement.
    """
    result = RotationResult()
    result.old_key_id = compromised_key_id

    # ---- Validation ----

    if signing_key_id == compromised_key_id:
        result.errors.append(
            "SECURITY VIOLATION: Cannot sign rotation with the compromised key. "
            "A surviving trusted authority must sign the rotation."
        )
        return result

    keys_path = backpack_root / "identity" / "keys.json"
    events_path = backpack_root / "events" / "events.ndjson"

    if not keys_path.is_file():
        result.errors.append("identity/keys.json not found")
        return result
    if not events_path.is_file():
        result.errors.append("events/events.ndjson not found")
        return result

    # Load and validate key registry
    keys_data = json.loads(keys_path.read_text(encoding="utf-8"))
    registry = {}
    for entry in keys_data.get("keys", []):
        registry[entry.get("key_id")] = entry

    # Verify compromised key exists
    if compromised_key_id not in registry:
        result.errors.append(
            f"Compromised key '{compromised_key_id}' not found in keys.json"
        )
        return result

    if registry[compromised_key_id].get("status") == "revoked":
        result.warnings.append(
            f"Key '{compromised_key_id}' is already revoked"
        )

    # Verify signing key exists and is active
    if signing_key_id not in registry:
        result.errors.append(
            f"Signing key '{signing_key_id}' not found in keys.json. "
            "It must be a pre-existing trusted authority."
        )
        return result

    if registry[signing_key_id].get("status") == "revoked":
        result.errors.append(
            f"Signing key '{signing_key_id}' is revoked. "
            "Cannot sign rotation with a revoked key."
        )
        return result

    # ---- Generate new keypair if needed ----

    if new_keypair is None:
        new_keypair = BackpackKeypair.generate()

    result.new_key_id = new_keypair.key_id

    # Determine roles for new key (inherit from old if not specified)
    if new_key_roles is None:
        old_roles = registry[compromised_key_id].get("roles", ["root"])
        new_key_roles = old_roles

    # ---- Step 1: KEY_REVOCATION event ----

    revocation_payload = {
        "revoked_key_id": compromised_key_id,
        "reason": "key_compromise",
        "trust_boundary_event_id": trust_boundary_event_id,
        "revoked_at_utc": _utc_now_iso(),
    }

    revocation_event = build_rotation_event(
        "KEY_REVOCATION", revocation_payload, actor, events_path
    )
    revocation_event = sign_event(
        revocation_event, signing_private_key, signing_key_id
    )
    append_event(events_path, revocation_event)
    result.revocation_event_id = revocation_event["event_id"]

    # ---- Step 2: KEY_PROMOTION event ----

    promotion_payload = {
        "new_key_id": new_keypair.key_id,
        "new_public_key_b64": new_keypair.public_key_b64,
        "algorithm": "Ed25519",
        "roles": new_key_roles,
        "promoted_by": signing_key_id,
        "replaces_key_id": compromised_key_id,
        "promoted_at_utc": _utc_now_iso(),
    }

    promotion_event = build_rotation_event(
        "KEY_PROMOTION", promotion_payload, actor, events_path
    )
    promotion_event = sign_event(
        promotion_event, signing_private_key, signing_key_id
    )
    append_event(events_path, promotion_event)
    result.promotion_event_id = promotion_event["event_id"]

    # ---- Step 3: Update keys.json ----

    # Mark compromised key as revoked
    for entry in keys_data["keys"]:
        if entry.get("key_id") == compromised_key_id:
            entry["status"] = "revoked"
            entry["revoked_at_utc"] = _utc_now_iso()
            entry["revocation_event_id"] = result.revocation_event_id
            break

    # Add new key
    new_key_entry = new_keypair.to_keys_entry(
        roles=new_key_roles,
        scopes=registry[compromised_key_id].get("scopes", ["all"]),
    )
    new_key_entry["promotion_event_id"] = result.promotion_event_id
    keys_data["keys"].append(new_key_entry)

    # Update revocations list
    keys_data.setdefault("revocations", []).append({
        "key_id": compromised_key_id,
        "revocation_event_id": result.revocation_event_id,
        "revoked_at_utc": _utc_now_iso(),
    })

    keys_path.write_text(
        json.dumps(keys_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    result.signed_by = signing_key_id
    result.success = True
    return result


# ---------------------------------------------------------------------------
# Verification: validate a rotation chain
# ---------------------------------------------------------------------------

def verify_rotation_events(
    backpack_root: Path,
) -> List[Dict[str, Any]]:
    """
    Scan the event log for KEY_REVOCATION and KEY_PROMOTION events
    and verify each one was signed by a key that was active at the time.

    Returns a list of verification results.
    """
    events_path = backpack_root / "events" / "events.ndjson"
    keys_path = backpack_root / "identity" / "keys.json"

    if not events_path.is_file() or not keys_path.is_file():
        return [{"error": "Missing events.ndjson or keys.json"}]

    # Load all keys (including revoked, for historical verification)
    keys_data = json.loads(keys_path.read_text(encoding="utf-8"))
    all_keys = {}
    for entry in keys_data.get("keys", []):
        kid = entry.get("key_id")
        pub_b64 = entry.get("public_key_b64")
        if kid and pub_b64:
            try:
                all_keys[kid] = load_public_key_b64(pub_b64)
            except Exception:
                pass

    results = []
    revoked_at_event: Dict[str, str] = {}  # key_id -> event_id where it was revoked

    events = []
    with events_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    for event in events:
        etype = event.get("type")
        if etype not in ("KEY_REVOCATION", "KEY_PROMOTION"):
            # Track revocations for ordering validation
            continue

        signer_kid = event.get("actor_key_id")
        event_id = event.get("event_id")

        check = {
            "event_id": event_id,
            "type": etype,
            "signer_key_id": signer_kid,
            "signature_present": bool(event.get("sig")),
            "signature_valid": False,
            "signer_was_active": True,
            "self_signed": False,
            "issues": [],
        }

        # Check if signer was already revoked
        if signer_kid in revoked_at_event:
            check["signer_was_active"] = False
            check["issues"].append(
                f"Signed by revoked key '{signer_kid}' "
                f"(revoked at event {revoked_at_event[signer_kid]})"
            )

        # Check for self-signing on revocation
        if etype == "KEY_REVOCATION":
            revoked_kid = event.get("payload", {}).get("revoked_key_id")
            if signer_kid == revoked_kid:
                check["self_signed"] = True
                check["issues"].append(
                    "SECURITY: Revocation is self-signed by the revoked key"
                )
            # Record the revocation
            if revoked_kid:
                revoked_at_event[revoked_kid] = event_id

        if etype == "KEY_PROMOTION":
            new_kid = event.get("payload", {}).get("new_key_id")
            if signer_kid == new_kid:
                check["self_signed"] = True
                check["issues"].append(
                    "SECURITY: Promotion is self-signed by the promoted key"
                )

        # Verify signature
        pub = all_keys.get(signer_kid)
        if pub:
            check["signature_valid"] = verify_event_signature(event, pub)
            if not check["signature_valid"]:
                check["issues"].append("Signature verification FAILED")
        else:
            check["issues"].append(
                f"Public key for signer '{signer_kid}' not found"
            )

        results.append(check)

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(
        description="Backpack v1.0 Key Rotation Protocol"
    )
    sub = ap.add_subparsers(dest="command")

    # Verify rotation history
    verify_p = sub.add_parser(
        "verify",
        help="Verify all rotation events in a backpack",
    )
    verify_p.add_argument("root", help="Backpack root directory")

    args = ap.parse_args()

    if args.command == "verify":
        results = verify_rotation_events(Path(args.root))
        for r in results:
            status = "OK" if (r.get("signature_valid") and not r.get("issues")) else "ISSUE"
            print(f"  [{status}] {r.get('type')} {r.get('event_id')}")
            for issue in r.get("issues", []):
                print(f"    ⚠ {issue}")
        if not results:
            print("  No rotation events found.")
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
