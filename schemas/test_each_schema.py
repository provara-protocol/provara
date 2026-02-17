#!/usr/bin/env python3
"""Test each event type schema individually"""
import sys
import json
from pathlib import Path
import jsonschema

# Load schema
schema_path = Path(__file__).parent / "event_types.json"
with open(schema_path, "r", encoding="utf-8") as f:
    full_schema = json.load(f)

# Ed25519 signature is 64 bytes -> 88 base64 chars (with == padding)
# Base64: every 3 bytes = 4 chars, 64 bytes = 64*4/3 = 85.33 -> 86 chars + 2 padding = 88 total
correct_sig = "A" * 86 + "=="

print(f"Correct signature length: {len(correct_sig)}", file=sys.stderr)

# Test GENESIS event against its specific schema
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
    "sig": correct_sig
}

# Test against genesis_event definition
genesis_schema = full_schema["definitions"]["genesis_event"]
print("\nTesting against genesis_event definition:", file=sys.stderr)
validator = jsonschema.Draft7Validator(genesis_schema)
errors = list(validator.iter_errors(event))
if errors:
    for error in errors:
        print(f"  ✗ {error.message}", file=sys.stderr)
        if error.path:
            print(f"    Path: {'.'.join(str(p) for p in error.path)}", file=sys.stderr)
else:
    print("  ✓ Passed", file=sys.stderr)

# Test against full schema with oneOf
print("\nTesting against full schema (oneOf):", file=sys.stderr)
validator = jsonschema.Draft7Validator(full_schema)
errors = list(validator.iter_errors(event))
if errors:
    for error in errors:
        print(f"  ✗ {error.message}", file=sys.stderr)
        if error.path:
            print(f"    Path: {'.'.join(str(p) for p in error.path)}", file=sys.stderr)
else:
    print("  ✓ Passed", file=sys.stderr)
    print("\nSUCCESS!")
