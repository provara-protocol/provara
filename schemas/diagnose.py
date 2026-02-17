#!/usr/bin/env python3
"""Diagnose schema validation issues"""
import sys
import json
from pathlib import Path
import jsonschema

# Load schema
schema_path = Path(__file__).parent / "event_types.json"
with open(schema_path, "r", encoding="utf-8") as f:
    schema = json.load(f)

# Test event
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

print(f"Signature length: {len(event['sig'])}", file=sys.stderr)
print(f"Signature: {event['sig']}", file=sys.stderr)

# Try validation with better error reporting
validator = jsonschema.Draft7Validator(schema)
errors = list(validator.iter_errors(event))

if errors:
    print(f"\n{len(errors)} validation errors found:", file=sys.stderr)
    for i, error in enumerate(errors, 1):
        print(f"\nError {i}:", file=sys.stderr)
        print(f"  Path: {'.'.join(str(p) for p in error.path)}", file=sys.stderr)
        print(f"  Message: {error.message}", file=sys.stderr)
        print(f"  Validator: {error.validator}", file=sys.stderr)
        if error.validator == 'pattern':
            print(f"  Pattern: {error.validator_value}", file=sys.stderr)
            print(f"  Value: {error.instance}", file=sys.stderr)
else:
    print("✓ Validation passed!", file=sys.stderr)
