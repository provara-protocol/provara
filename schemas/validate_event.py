#!/usr/bin/env python3
"""
validate_event.py — Validate Provara events against JSON Schema

Usage:
    python validate_event.py <event_file.json>
    python validate_event.py --stdin < event.json
    echo '{"type":"OBSERVATION",...}' | python validate_event.py --stdin

Exit codes:
    0 - Valid
    1 - Invalid
    2 - Error (file not found, malformed JSON, etc.)
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import jsonschema
    from jsonschema import validate, ValidationError
except ImportError:
    print("Error: jsonschema package not found", file=sys.stderr)
    print("Install it with: pip install jsonschema", file=sys.stderr)
    sys.exit(2)


def load_schema():
    """Load the event_types.json schema."""
    schema_path = Path(__file__).parent / "event_types.json"
    if not schema_path.exists():
        print(f"Error: Schema not found at {schema_path}", file=sys.stderr)
        sys.exit(2)
    
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_event(event: dict, schema: dict, verbose: bool = False) -> bool:
    """
    Validate an event against the schema.
    
    Returns:
        True if valid, False if invalid
    """
    try:
        validate(instance=event, schema=schema)
        
        if verbose:
            print(f"✓ Valid {event.get('type', 'UNKNOWN')} event", file=sys.stderr)
            print(f"  event_id: {event.get('event_id', 'N/A')}", file=sys.stderr)
            print(f"  actor: {event.get('actor', 'N/A')}", file=sys.stderr)
        
        return True
    
    except ValidationError as e:
        print(f"✗ Validation failed:", file=sys.stderr)
        print(f"  Event type: {event.get('type', 'UNKNOWN')}", file=sys.stderr)
        print(f"  Error: {e.message}", file=sys.stderr)
        
        if e.path:
            path_str = ".".join(str(p) for p in e.path)
            print(f"  Path: {path_str}", file=sys.stderr)
        
        if verbose:
            print(f"\n  Full error:", file=sys.stderr)
            print(f"  {e}", file=sys.stderr)
        
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Validate Provara events against JSON Schema"
    )
    parser.add_argument(
        "event_file",
        nargs="?",
        help="Path to event JSON file (omit to use --stdin)"
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read event from stdin"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Load schema
    schema = load_schema()
    
    # Read event
    if args.stdin:
        try:
            event = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON from stdin: {e}", file=sys.stderr)
            sys.exit(2)
    elif args.event_file:
        event_path = Path(args.event_file)
        if not event_path.exists():
            print(f"Error: File not found: {event_path}", file=sys.stderr)
            sys.exit(2)
        
        try:
            with open(event_path, "r", encoding="utf-8") as f:
                event = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {event_path}: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        parser.print_help()
        sys.exit(2)
    
    # Validate
    is_valid = validate_event(event, schema, verbose=args.verbose)
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
