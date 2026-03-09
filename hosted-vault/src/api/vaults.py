"""
Provara Hosted Vault API - Vault Management Endpoints

Endpoints:
- POST   /api/v1/vaults          - Create a new vault
- GET    /api/v1/vaults          - List user's vaults
- GET    /api/v1/vaults/:id      - Get vault details
- DELETE /api/v1/vaults/:id      - Delete a vault
"""

import json
import os
from http import HTTPStatus
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from supabase import Client, create_client

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

supabase: Client = create_client(supabase_url, supabase_key)


def generate_keypair() -> Dict[str, str]:
    """Generate Ed25519 keypair for new vault."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # PEM encoding
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    # Key fingerprint (Provara-compatible: bp1_ + 16 hex chars)
    import hashlib

    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = f"bp1_{hashlib.sha256(public_bytes).hexdigest()[:16]}"

    return {
        "key_id": key_id,
        "public_key_pem": public_pem,
        "private_key_pem": private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8"),
    }


def create_vault(owner_id: str, name: str, description: Optional[str] = None) -> Dict[str, Any]:
    """Create a new vault for the user."""
    # Generate keypair
    keypair = generate_keypair()

    # Create vault record
    vault_data = {
        "owner_id": owner_id,
        "name": name,
        "description": description,
        "tier": "free",
        "status": "active",
        "public_key": keypair["public_key_pem"],
        "key_id": keypair["key_id"],
    }

    result = supabase.table("vaults").insert(vault_data).execute()

    if not result.data:
        raise Exception("Failed to create vault")

    vault = result.data[0]

    # Store private key in Supabase Secrets (via RPC or direct table insert)
    # For MVP, we'll store encrypted in a separate table
    supabase.table("vault_keys").insert(
        {
            "vault_id": vault["id"],
            "encrypted_private_key": keypair["private_key_pem"],  # TODO: Encrypt with KMS
            "key_id": keypair["key_id"],
        }
    ).execute()

    # Initialize empty events.ndjson in Storage
    supabase.storage.from_("vaults").upload(
        f"{vault['id']}/events/events.ndjson",
        b"",
        {"content-type": "application/x-ndjson"},
    )

    # Create genesis.json
    genesis = {
        "vault_id": vault["id"],
        "key_id": keypair["key_id"],
        "created_at": vault["created_at"],
        "algorithm": "Ed25519",
        "protocol": "Provara v1.0",
    }
    supabase.storage.from_("vaults").upload(
        f"{vault['id']}/identity/genesis.json",
        json.dumps(genesis, indent=2).encode("utf-8"),
        {"content-type": "application/json"},
    )

    return {
        "vault_id": vault["id"],
        "name": vault["name"],
        "key_id": keypair["key_id"],
        "created_at": vault["created_at"],
        "tier": vault["tier"],
    }


def get_vault(vault_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
    """Get vault details by ID."""
    result = (
        supabase.table("vaults")
        .select("id, owner_id, name, description, tier, status, key_id, created_at, updated_at, last_event_seq, merkle_root")
        .eq("id", vault_id)
        .eq("owner_id", owner_id)
        .execute()
    )

    return result.data[0] if result.data else None


def list_vaults(owner_id: str) -> list:
    """List all vaults for a user."""
    result = (
        supabase.table("vaults")
        .select("id, name, tier, status, key_id, created_at, last_event_seq")
        .eq("owner_id", owner_id)
        .eq("status", "active")
        .order("created_at", desc=True)
        .execute()
    )

    return result.data or []


def delete_vault(vault_id: str, owner_id: str) -> bool:
    """Soft-delete a vault."""
    result = (
        supabase.table("vaults")
        .update({"status": "deleted"})
        .eq("id", vault_id)
        .eq("owner_id", owner_id)
        .execute()
    )

    return result.data is not None and len(result.data) > 0


# Vercel serverless function handler
def handler(request):
    """Main request handler for vaults endpoint."""
    # CORS headers
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }

    # Handle preflight
    if request.method == "OPTIONS":
        return {"statusCode": HTTPStatus.OK, "headers": headers, "body": ""}

    # Get auth header (Clerk JWT)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {
            "statusCode": HTTPStatus.UNAUTHORIZED,
            "headers": headers,
            "body": json.dumps({"error": "Missing or invalid Authorization header"}),
        }

    # TODO: Verify Clerk JWT token
    # For MVP, extract user_id from token (full verification in production)
    token = auth_header[7:]  # Remove "Bearer " prefix
    # In production: verify with clerk_backend.verify_jwt(token)
    owner_id = "user_placeholder"  # TODO: Extract from verified JWT

    try:
        if request.method == "POST":
            # Create vault
            body = json.loads(request.body or "{}")
            name = body.get("name")
            if not name:
                return {
                    "statusCode": HTTPStatus.BAD_REQUEST,
                    "headers": headers,
                    "body": json.dumps({"error": "name is required"}),
                }

            vault = create_vault(owner_id, name, body.get("description"))
            return {
                "statusCode": HTTPStatus.CREATED,
                "headers": headers,
                "body": json.dumps(vault),
            }

        elif request.method == "GET":
            # List or get vault
            vault_id = request.path_params.get("id") if hasattr(request, "path_params") else None

            if vault_id:
                vault = get_vault(vault_id, owner_id)
                if not vault:
                    return {
                        "statusCode": HTTPStatus.NOT_FOUND,
                        "headers": headers,
                        "body": json.dumps({"error": "Vault not found"}),
                    }
                return {
                    "statusCode": HTTPStatus.OK,
                    "headers": headers,
                    "body": json.dumps(vault),
                }
            else:
                vaults = list_vaults(owner_id)
                return {
                    "statusCode": HTTPStatus.OK,
                    "headers": headers,
                    "body": json.dumps({"vaults": vaults}),
                }

        elif request.method == "DELETE":
            vault_id = request.path_params.get("id") if hasattr(request, "path_params") else None
            if not vault_id:
                return {
                    "statusCode": HTTPStatus.BAD_REQUEST,
                    "headers": headers,
                    "body": json.dumps({"error": "Vault ID required"}),
                }

            success = delete_vault(vault_id, owner_id)
            if not success:
                return {
                    "statusCode": HTTPStatus.NOT_FOUND,
                    "headers": headers,
                    "body": json.dumps({"error": "Vault not found"}),
                }

            return {
                "statusCode": HTTPStatus.NO_CONTENT,
                "headers": headers,
                "body": "",
            }

        else:
            return {
                "statusCode": HTTPStatus.METHOD_NOT_ALLOWED,
                "headers": headers,
                "body": json.dumps({"error": "Method not allowed"}),
            }

    except Exception as e:
        return {
            "statusCode": HTTPStatus.INTERNAL_SERVER_ERROR,
            "headers": headers,
            "body": json.dumps({"error": str(e)}),
        }
