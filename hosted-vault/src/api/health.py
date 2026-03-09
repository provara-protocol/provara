"""
Provara Hosted Vault API - Health Check Endpoint

Endpoint:
- GET /api/health - System health status
"""

import json
import os
from http import HTTPStatus
from datetime import datetime, timezone

from supabase import Client, create_client


def check_supabase_health() -> dict:
    """Check Supabase database connectivity."""
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

        if not supabase_url or not supabase_key:
            return {"status": "error", "message": "Supabase credentials not configured"}

        client: Client = create_client(supabase_url, supabase_key)

        # Simple query to test connection
        result = client.table("vaults").select("id").limit(1).execute()
        return {"status": "healthy", "latency_ms": "N/A"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


def check_clerk_health() -> dict:
    """Check Clerk authentication service."""
    try:
        clerk_key = os.environ.get("CLERK_SECRET_KEY")
        if not clerk_key:
            return {"status": "error", "message": "Clerk credentials not configured"}

        # TODO: Actual Clerk API health check
        return {"status": "healthy", "message": "Clerk configured"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


def check_storage_health() -> dict:
    """Check Supabase Storage bucket access."""
    try:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

        if not supabase_url or not supabase_key:
            return {"status": "error", "message": "Storage credentials not configured"}

        client: Client = create_client(supabase_url, supabase_key)

        # Try to list buckets
        buckets = client.storage.list_buckets()
        vault_bucket = next((b for b in buckets if b.name == "vaults"), None)

        if not vault_bucket:
            return {"status": "warning", "message": "Vaults bucket not found"}

        return {"status": "healthy", "bucket": "vaults"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


def handler(request):
    """Health check endpoint handler."""
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Content-Type": "application/json",
    }

    # Handle preflight
    if request.method == "OPTIONS":
        return {"statusCode": HTTPStatus.OK, "headers": headers, "body": ""}

    if request.method != "GET":
        return {
            "statusCode": HTTPStatus.METHOD_NOT_ALLOWED,
            "headers": headers,
            "body": json.dumps({"error": "Method not allowed"}),
        }

    # Run health checks
    checks = {
        "supabase": check_supabase_health(),
        "clerk": check_clerk_health(),
        "storage": check_storage_health(),
    }

    # Determine overall status
    all_healthy = all(check["status"] in ["healthy", "warning"] for check in checks.values())
    any_unhealthy = any(check["status"] == "unhealthy" for check in checks.values())

    overall_status = "healthy" if all_healthy else "unhealthy" if any_unhealthy else "degraded"

    response = {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
        "checks": checks,
    }

    status_code = HTTPStatus.OK if overall_status == "healthy" else HTTPStatus.SERVICE_UNAVAILABLE

    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(response, indent=2),
    }
