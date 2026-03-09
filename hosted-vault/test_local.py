#!/usr/bin/env python3
"""
Provara Hosted Vault - Local Testing Script

Tests the API endpoints locally before deployment.
Requires a running local server (vercel dev or similar).
"""

import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Configuration
BASE_URL = os.environ.get("VAULT_API_URL", "http://localhost:3000")
CLERK_TOKEN = os.environ.get("CLERK_TEST_TOKEN", "")  # Get from Clerk dashboard

# Test vault storage
test_vault_id = None


def make_request(method, path, data=None, headers=None):
    """Make HTTP request to API."""
    url = f"{BASE_URL}{path}"
    headers = headers or {}
    headers["Content-Type"] = "application/json"
    
    if CLERK_TOKEN:
        headers["Authorization"] = f"Bearer {CLERK_TOKEN}"
    
    body = json.dumps(data).encode("utf-8") if data else None
    
    req = Request(url, data=body, headers=headers, method=method)
    
    try:
        with urlopen(req) as response:
            return {
                "status": response.status,
                "body": json.loads(response.read().decode("utf-8")),
            }
    except HTTPError as e:
        return {
            "status": e.code,
            "body": json.loads(e.read().decode("utf-8")) if e.fp else {},
        }
    except URLError as e:
        return {"status": 0, "body": {"error": str(e)}}


def test_health():
    """Test health check endpoint."""
    print("\n🏥 Testing /api/health...")
    result = make_request("GET", "/api/health")
    
    if result["status"] == 200:
        print(f"   ✓ Health check passed (status: {result['body'].get('status')})")
        return True
    else:
        print(f"   ✗ Health check failed: {result['body']}")
        return False


def test_create_vault():
    """Test vault creation."""
    global test_vault_id
    
    print("\n🏗️  Testing POST /api/v1/vaults...")
    result = make_request(
        "POST",
        "/api/v1/vaults",
        {"name": "test-vault", "description": "Local test vault"},
    )
    
    if result["status"] == 201:
        test_vault_id = result["body"].get("vault_id")
        print(f"   ✓ Vault created: {test_vault_id}")
        return True
    else:
        print(f"   ✗ Vault creation failed: {result['body']}")
        return False


def test_list_vaults():
    """Test vault listing."""
    print("\n📋 Testing GET /api/v1/vaults...")
    result = make_request("GET", "/api/v1/vaults")
    
    if result["status"] == 200:
        vaults = result["body"].get("vaults", [])
        print(f"   ✓ Listed {len(vaults)} vault(s)")
        return True
    else:
        print(f"   ✗ Vault listing failed: {result['body']}")
        return False


def test_append_event():
    """Test event append."""
    if not test_vault_id:
        print("\n⏭️  Skipping event append (no vault ID)")
        return False
    
    print(f"\n📝 Testing POST /api/v1/vaults/{test_vault_id}/events...")
    result = make_request(
        "POST",
        f"/api/v1/vaults/{test_vault_id}/events",
        {
            "event_type": "note",
            "data": {"message": "Test event from local script", "test": True},
        },
    )
    
    if result["status"] == 201:
        event_id = result["body"].get("event_id")
        print(f"   ✓ Event appended: {event_id}")
        return True
    else:
        print(f"   ✗ Event append failed: {result['body']}")
        return False


def test_query_events():
    """Test event query."""
    if not test_vault_id:
        print("\n⏭️  Skipping event query (no vault ID)")
        return False
    
    print(f"\n🔍 Testing GET /api/v1/vaults/{test_vault_id}/events...")
    result = make_request("GET", f"/api/v1/vaults/{test_vault_id}/events?last=10")
    
    if result["status"] == 200:
        events = result["body"].get("events", [])
        print(f"   ✓ Queried {len(events)} event(s)")
        return True
    else:
        print(f"   ✗ Event query failed: {result['body']}")
        return False


def test_verify_vault():
    """Test vault verification."""
    if not test_vault_id:
        print("\n⏭️  Skipping vault verify (no vault ID)")
        return False
    
    print(f"\n✅ Testing GET /api/v1/vaults/{test_vault_id}/events?action=verify...")
    result = make_request("GET", f"/api/v1/vaults/{test_vault_id}/events?action=verify")
    
    if result["status"] == 200:
        valid = result["body"].get("valid")
        print(f"   ✓ Vault verification: {'PASS' if valid else 'FAIL'}")
        return valid
    else:
        print(f"   ✗ Vault verification failed: {result['body']}")
        return False


def run_all_tests():
    """Run all tests in sequence."""
    print("=" * 60)
    print("🧪 Provara Hosted Vault - Local Test Suite")
    print("=" * 60)
    print(f"\nAPI URL: {BASE_URL}")
    print(f"Auth: {'Clerk JWT' if CLERK_TOKEN else 'None (will fail auth)'}")
    
    tests = [
        ("Health Check", test_health),
        ("Create Vault", test_create_vault),
        ("List Vaults", test_list_vaults),
        ("Append Event", test_append_event),
        ("Query Events", test_query_events),
        ("Verify Vault", test_verify_vault),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"   ✗ Unexpected error: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, passed_test in results:
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed")
        return 1


if __name__ == "__main__":
    if "--help" in sys.argv:
        print("""
Provara Hosted Vault - Local Test Script

Usage:
    python test_local.py                    # Run with defaults
    VAULT_API_URL=http://localhost:3000 python test_local.py
    CLERK_TEST_TOKEN=xxx python test_local.py

Environment Variables:
    VAULT_API_URL     - API base URL (default: http://localhost:3000)
    CLERK_TEST_TOKEN  - JWT token from Clerk (required for auth tests)
        """)
        sys.exit(0)
    
    sys.exit(run_all_tests())
