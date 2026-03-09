"""
Provara Hosted Vault API - Event Management Endpoints

Endpoints:
- POST /api/v1/vaults/:id/events        - Append event to vault
- GET  /api/v1/vaults/:id/events        - Query events from vault
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

supabase: Client = create_client(supabase_url, supabase_key)

# Import Provara canonical JSON for hashing
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent.parent
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

try:
    from provara.canonical_json import canonical_dumps, canonical_hash
except ImportError:
    # Fallback canonical JSON implementation
    def canonical_dumps(obj: Dict) -> str:
        return json.dumps(obj, sort_keys=True, separators=(",", ":"))

    def canonical_hash(obj: Dict) -> str:
        return hashlib.sha256(canonical_dumps(obj).encode("utf-8")).hexdigest()


# Valid Provara event types
VALID_EVENT_TYPES = [
    "OBSERVATION",
    "ASSERTION",
    "ATTESTATION",
    "RETRACTION",
    "KEY_ROTATION",
    "KEY_REVOCATION",
    "KEY_PROMOTION",
]

# MVP event types (simplified)
MVP_EVENT_TYPES = ["identity", "decision", "belief", "note", "milestone", "reflection", "correction"]

MAX_EVENT_PAYLOAD_BYTES = int(os.environ.get("MAX_EVENT_PAYLOAD_BYTES", 10240))  # 10KB


def get_vault_key(vault_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve vault's private key for signing."""
    result = supabase.table("vault_keys").select("encrypted_private_key, key_id").eq("vault_id", vault_id).execute()
    return result.data[0] if result.data else None


def get_vault_info(vault_id: str) -> Optional[Dict[str, Any]]:
    """Get vault metadata."""
    result = supabase.table("vaults").select("id, owner_id, status, last_event_seq, merkle_root").eq("id", vault_id).execute()
    return result.data[0] if result.data else None


def check_usage_quota(vault_id: str, tier: str) -> tuple[bool, str]:
    """Check if vault has exceeded its event quota."""
    # Get current month usage
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    result = (
        supabase.table("usage_tracking")
        .select("event_count")
        .eq("vault_id", vault_id)
        .eq("month", month_start.date().isoformat())
        .execute()
    )

    current_count = result.data[0]["event_count"] if result.data else 0

    # Tier limits
    limits = {"free": 100, "developer": 10000, "team": 100000, "enterprise": -1}
    max_events = limits.get(tier, 100)

    if max_events > 0 and current_count >= max_events:
        return False, f"Monthly event limit reached ({max_events})"

    return True, ""


def sign_event(private_key_pem: str, event_hash: str) -> str:
    """Sign event hash with Ed25519 private key."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=None,
    )

    signature = private_key.sign(event_hash.encode("utf-8"))
    return signature.hex()


def append_event(
    vault_id: str,
    event_type: str,
    data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append a new event to the vault."""
    # Get vault info
    vault = get_vault_info(vault_id)
    if not vault:
        raise ValueError("Vault not found")

    if vault["status"] != "active":
        raise ValueError("Vault is not active")

    # Get vault key
    key_info = get_vault_key(vault_id)
    if not key_info:
        raise ValueError("Vault key not found")

    # Check quota
    vault_details = supabase.table("vaults").select("tier").eq("id", vault_id).execute()
    tier = vault_details.data[0]["tier"] if vault_details.data else "free"
    allowed, error_msg = check_usage_quota(vault_id, tier)
    if not allowed:
        raise ValueError(error_msg)

    # Validate event type
    if event_type not in MVP_EVENT_TYPES:
        raise ValueError(f"Invalid event_type. Valid: {MVP_EVENT_TYPES}")

    # Validate payload size
    payload_bytes = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(payload_bytes) > MAX_EVENT_PAYLOAD_BYTES:
        raise ValueError(f"Event payload exceeds {MAX_EVENT_PAYLOAD_BYTES} bytes")

    # Build event
    seq = vault["last_event_seq"]
    prev_hash = vault["merkle_root"] or ("0" * 64)  # Genesis
    timestamp = datetime.now(timezone.utc).isoformat()

    event = {
        "event_type": event_type,
        "seq": seq,
        "timestamp": timestamp,
        "prev_hash": prev_hash,
        "data": data,
    }

    if metadata:
        event["metadata"] = metadata

    # Compute hash
    event_hash = canonical_hash(event)

    # Sign event
    signature = sign_event(key_info["encrypted_private_key"], event_hash)

    # Build event_id (evt_ + first 24 chars of hash)
    event_id = f"evt_{event_hash[:24]}"

    # Insert into database
    event_record = {
        "vault_id": vault_id,
        "event_id": event_id,
        "event_type": event_type,
        "seq": seq,
        "timestamp": timestamp,
        "event_data": data,
        "hash": event_hash,
        "prev_hash": prev_hash,
        "signature": signature,
        "actor_key_id": key_info["key_id"],
        "metadata": metadata,
    }

    supabase.table("events").insert(event_record).execute()

    # Append to events.ndjson in Storage
    ndjson_line = canonical_dumps(event) + "\n"
    storage_path = f"{vault_id}/events/events.ndjson"

    # Get existing content and append
    try:
        existing = supabase.storage.from_("vaults").download(storage_path)
        new_content = existing + ndjson_line.encode("utf-8")
    except Exception:
        new_content = ndjson_line.encode("utf-8")

    supabase.storage.from_("vaults").upload(
        storage_path,
        new_content,
        {"content-type": "application/x-ndjson"},
    )

    # Update vault's last_event_seq and merkle_root
    supabase.table("vaults").update(
        {"last_event_seq": seq + 1, "merkle_root": event_hash, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", vault_id).execute()

    # Update usage tracking
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).date().isoformat()
    supabase.table("usage_tracking").upsert(
        {"vault_id": vault_id, "month": month_start, "event_count": 1}, on_conflict="vault_id,month"
    ).execute()

    # Compute new state hash
    state_hash = hashlib.sha256(f"{event_hash}{seq}".encode("utf-8")).hexdigest()

    return {
        "event_id": event_id,
        "hash": event_hash,
        "seq": seq,
        "timestamp": timestamp,
        "state_hash": state_hash,
    }


def query_events(
    vault_id: str,
    last: Optional[int] = 50,
    event_type: Optional[str] = None,
    since: Optional[str] = None,
    format: str = "json",
) -> Dict[str, Any]:
    """Query events from vault."""
    # Verify vault access
    vault = get_vault_info(vault_id)
    if not vault:
        raise ValueError("Vault not found")

    # Build query
    query = supabase.table("events").select("*").eq("vault_id", vault_id)

    if event_type:
        query = query.eq("event_type", event_type)

    if since:
        query = query.gte("timestamp", since)

    # Order by sequence descending (most recent first)
    query = query.order("seq", desc=True)

    if last:
        query = query.limit(min(last, 1000))  # Max 1000 events

    result = query.execute()
    events = result.data or []

    # Reverse to get chronological order
    events.reverse()

    # Format response
    if format == "ndjson":
        ndjson_content = "\n".join(canonical_dumps(e) for e in events)
        return {"content": ndjson_content, "format": "ndjson", "count": len(events)}
    else:
        # JSON format
        formatted_events = []
        for e in events:
            formatted_events.append(
                {
                    "event_id": e["event_id"],
                    "type": e["event_type"],
                    "seq": e["seq"],
                    "timestamp": e["timestamp"],
                    "data": e["event_data"],
                    "hash": e["hash"],
                    "prev_hash": e["prev_hash"],
                }
            )

        return {
            "vault_id": vault_id,
            "count": len(formatted_events),
            "events": formatted_events,
            "merkle_root": vault["merkle_root"],
        }


def verify_vault_chain(vault_id: str) -> Dict[str, Any]:
    """Verify the integrity of a vault's event chain."""
    vault = get_vault_info(vault_id)
    if not vault:
        return {"valid": False, "error": "Vault not found"}

    # Get all events
    result = supabase.table("events").select("*").eq("vault_id", vault_id).order("seq").execute()
    events = result.data or []

    if not events:
        return {"valid": True, "events_checked": 0, "message": "Empty vault"}

    # Verify chain
    expected_prev = "0" * 64  # Genesis
    errors = []

    for i, event in enumerate(events):
        # Check prev_hash linkage
        if event["prev_hash"] != expected_prev:
            errors.append(f"seq {i}: prev_hash mismatch")

        # Verify hash chain
        if i > 0:
            prev_event = events[i - 1]
            if event["prev_hash"] != prev_event["hash"]:
                errors.append(f"seq {i}: hash chain broken")

        expected_prev = event["hash"]

    # Verify final merkle_root matches
    if events and vault["merkle_root"] != events[-1]["hash"]:
        errors.append(f"merkle_root mismatch: stored={vault['merkle_root']}, computed={events[-1]['hash']}")

    return {
        "valid": len(errors) == 0,
        "events_checked": len(events),
        "errors": errors,
        "merkle_root": vault["merkle_root"],
        "last_event_hash": events[-1]["hash"] if events else None,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }


# Vercel serverless function handler
def handler(request):
    """Main request handler for events endpoint."""
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }

    # Handle preflight
    if request.method == "OPTIONS":
        return {"statusCode": HTTPStatus.OK, "headers": headers, "body": ""}

    # Get auth header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {
            "statusCode": HTTPStatus.UNAUTHORIZED,
            "headers": headers,
            "body": json.dumps({"error": "Missing or invalid Authorization header"}),
        }

    # TODO: Verify Clerk JWT
    owner_id = "user_placeholder"  # Extract from verified JWT

    # Extract vault_id from path
    vault_id = request.path_params.get("id") if hasattr(request, "path_params") else None
    if not vault_id:
        return {
            "statusCode": HTTPStatus.BAD_REQUEST,
            "headers": headers,
            "body": json.dumps({"error": "Vault ID required"}),
        }

    try:
        if request.method == "POST":
            # Append event
            body = json.loads(request.body or "{}")
            event_type = body.get("event_type")
            data = body.get("data", {})
            metadata = body.get("metadata")

            if not event_type:
                return {
                    "statusCode": HTTPStatus.BAD_REQUEST,
                    "headers": headers,
                    "body": json.dumps({"error": "event_type is required"}),
                }

            if not isinstance(data, dict):
                return {
                    "statusCode": HTTPStatus.BAD_REQUEST,
                    "headers": headers,
                    "body": json.dumps({"error": "data must be an object"}),
                }

            result = append_event(vault_id, event_type, data, metadata)
            return {
                "statusCode": HTTPStatus.CREATED,
                "headers": headers,
                "body": json.dumps(result),
            }

        elif request.method == "GET":
            # Query events or verify
            action = request.query_params.get("action", "query")

            if action == "verify":
                result = verify_vault_chain(vault_id)
                return {
                    "statusCode": HTTPStatus.OK,
                    "headers": headers,
                    "body": json.dumps(result),
                }
            else:
                # Query events
                last = request.query_params.get("last", 50, int)
                event_type = request.query_params.get("type")
                since = request.query_params.get("since")
                format = request.query_params.get("format", "json")

                result = query_events(vault_id, last, event_type, since, format)

                if format == "ndjson":
                    headers["Content-Type"] = "application/x-ndjson"
                    return {
                        "statusCode": HTTPStatus.OK,
                        "headers": headers,
                        "body": result["content"],
                    }
                else:
                    return {
                        "statusCode": HTTPStatus.OK,
                        "headers": headers,
                        "body": json.dumps(result),
                    }

        else:
            return {
                "statusCode": HTTPStatus.METHOD_NOT_ALLOWED,
                "headers": headers,
                "body": json.dumps({"error": "Method not allowed"}),
            }

    except ValueError as e:
        return {
            "statusCode": HTTPStatus.BAD_REQUEST,
            "headers": headers,
            "body": json.dumps({"error": str(e)}),
        }
    except Exception as e:
        return {
            "statusCode": HTTPStatus.INTERNAL_SERVER_ERROR,
            "headers": headers,
            "body": json.dumps({"error": str(e)}),
        }
