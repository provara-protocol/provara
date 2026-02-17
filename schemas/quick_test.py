#!/usr/bin/env python3
"""Quick test to verify schema validation"""
import sys
print("Python:", sys.version, file=sys.stderr)
print("Starting test...", file=sys.stderr)

try:
    import jsonschema
    print("✓ jsonschema imported", file=sys.stderr)
except ImportError as e:
    print(f"✗ jsonschema import failed: {e}", file=sys.stderr)
    sys.exit(1)

import json
from pathlib import Path

# Load schema
schema_path = Path(__file__).parent / "event_types.json"
print(f"Loading schema from: {schema_path}", file=sys.stderr)
with open(schema_path, "r", encoding="utf-8") as f:
    schema = json.load(f)
print("✓ Schema loaded", file=sys.stderr)

# Test valid event
event = {
    "event_id": "evt_abc123def456789012345678",
    "type": "GENESIS",
    "namespace": "canonical",
    "actor": "bp1_0123456789abcdef",
    "actor_key_id": "bp1_0123456789abcdef",
    "ts_logical": 0,
    "prev_event_hash": None,
    "timestamp_utc": "2026-02-16T10:00:00Z",
    "payload": {
        "uid": "550e8400-e29b-41d4-a716-446655440000",
        "created_at_utc": "2026-02-16T10:00:00Z",
        "root_key_id": "bp1_0123456789abcdef",
        "actor": "genesis"
    },
    "sig": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
}

try:
    jsonschema.validate(instance=event, schema=schema)
    print("✓ Valid GENESIS event passed", file=sys.stderr)
except jsonschema.ValidationError as e:
    print(f"✗ Validation failed: {e.message}", file=sys.stderr)
    sys.exit(1)

# Test invalid event ID
event_bad = event.copy()
event_bad["event_id"] = "bad_id"

try:
    jsonschema.validate(instance=event_bad, schema=schema)
    print("✗ Invalid event should have failed!", file=sys.stderr)
    sys.exit(1)
except jsonschema.ValidationError:
    print("✓ Invalid event correctly rejected", file=sys.stderr)

print("\nAll tests passed!", file=sys.stderr)
print("SUCCESS")
