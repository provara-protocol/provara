#!/usr/bin/env python3
"""
provara_cli.py — Command-line interface for Provara operations

Wraps common Provara operations with a friendly CLI.
Uses the same backend as the MCP server.

Usage:
    provara init <path> [--quorum]
    provara verify <path>
    provara state <path>
    provara sync <local> <remote>
    provara export <path> --output <file> [--since <hash>]
    provara import <path> --delta <file>

Examples:
    provara init ./my_vault --quorum
    provara state ./my_vault
    provara sync ./vault1 ./vault2
    provara export ./vault1 --output delta.ndjson
    provara import ./vault2 --delta delta.ndjson
"""

import argparse
import json
import sys
from pathlib import Path

# Add SNP_Core/bin to path
from provara.bootstrap_v0 import bootstrap_backpack
from provara.reducer_v0 import SovereignReducerV0
from provara.sync_v0 import sync_backpacks, verify_causal_chain, load_events, export_delta, import_delta
from provara.canonical_json import canonical_dumps


def cmd_init(args):
    """Initialize a new Provara vault."""
    path = Path(args.path)
    
    if path.exists() and any(path.iterdir()):
        print(f"Error: Directory {path} already exists and is not empty", file=sys.stderr)
        return 1
    
    print(f"Creating vault at: {path}")
    result = bootstrap_backpack(
        path,
        actor=args.actor,
        include_quorum=args.quorum,
        quiet=False
    )
    
    if not result.success:
        print("Bootstrap failed:", file=sys.stderr)
        for error in result.errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    
    print(f"\n✅ Vault created successfully!")
    print(f"   UID: {result.uid}")
    print(f"   Root key: {result.root_key_id}")
    if result.quorum_key_id:
        print(f"   Quorum key: {result.quorum_key_id}")
    print(f"   Merkle root: {result.merkle_root}")
    print(f"\n⚠️  Private keys written to: {path.parent / 'my_private_keys.json'}")
    print("   Store them securely!")
    
    return 0


def cmd_verify(args):
    """Verify vault integrity."""
    path = Path(args.path)
    events_path = path / "events" / "events.ndjson"
    
    if not events_path.exists():
        print(f"Error: Vault not found at {path}", file=sys.stderr)
        return 1
    
    print(f"Verifying: {path}")
    
    # Load and verify chains
    events = load_events(events_path)
    actors = {e.get("actor") for e in events if e.get("actor")}
    
    print(f"  Events: {len(events)}")
    print(f"  Actors: {len(actors)}")
    
    all_valid = True
    for actor in sorted(actors):
        valid = verify_causal_chain(events, actor)
        status = "✓" if valid else "✗"
        print(f"  {status} Chain for {actor[:20]}...")
        if not valid:
            all_valid = False
    
    if all_valid:
        print("\n✅ All chains valid")
        return 0
    else:
        print("\n❌ Chain verification failed", file=sys.stderr)
        return 1


def cmd_state(args):
    """Export and display vault state."""
    path = Path(args.path)
    events_path = path / "events" / "events.ndjson"
    
    if not events_path.exists():
        print(f"Error: Vault not found at {path}", file=sys.stderr)
        return 1
    
    print(f"Computing state for: {path}")
    
    events = load_events(events_path)
    reducer = SovereignReducerV0()
    reducer.apply_events(events)
    state = reducer.export_state()
    
    meta = state["metadata"]
    
    print(f"\n📊 State Summary:")
    print(f"   Events processed: {meta['event_count']}")
    print(f"   State hash: {meta['state_hash']}")
    print(f"   Canonical beliefs: {len(state['canonical'])}")
    print(f"   Local beliefs: {len(state['local'])}")
    print(f"   Contested beliefs: {len(state['contested'])}")
    print(f"   Archived entries: {sum(len(v) if isinstance(v, list) else 1 for v in state['archived'].values())}")
    
    if args.json:
        print("\n" + canonical_dumps(state))
    
    return 0


def cmd_sync(args):
    """Sync two vaults."""
    local = Path(args.local)
    remote = Path(args.remote)
    
    if not (local / "events" / "events.ndjson").exists():
        print(f"Error: Local vault not found at {local}", file=sys.stderr)
        return 1
    if not (remote / "events" / "events.ndjson").exists():
        print(f"Error: Remote vault not found at {remote}", file=sys.stderr)
        return 1
    
    print(f"Syncing: {local} ← {remote}")
    
    result = sync_backpacks(local, remote)
    
    if not result.success:
        print("\n❌ Sync failed:", file=sys.stderr)
        for error in result.errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    
    print(f"\n✅ Sync complete!")
    print(f"   Events merged: {result.events_merged}")
    print(f"   New state hash: {result.new_state_hash}")
    if result.forks:
        print(f"\n⚠️  Forks detected: {len(result.forks)}")
        for fork in result.forks:
            print(f"   Actor: {fork.actor_id}, prev_hash: {fork.prev_hash}")
    
    return 0


def cmd_export(args):
    """Export delta bundle."""
    path = Path(args.path)
    output = Path(args.output)
    
    if not (path / "events" / "events.ndjson").exists():
        print(f"Error: Vault not found at {path}", file=sys.stderr)
        return 1
    
    print(f"Exporting delta from: {path}")
    if args.since:
        print(f"  Since: {args.since}")
    else:
        print("  Mode: full export (all events)")
    
    delta_bytes = export_delta(path, since_hash=args.since)
    output.write_bytes(delta_bytes)
    
    # Count events
    lines = delta_bytes.decode("utf-8").strip().split("\n")
    event_count = len(lines) - 1 if len(lines) > 1 else 0
    
    print(f"\n✅ Delta exported")
    print(f"   Output: {output}")
    print(f"   Events: {event_count}")
    print(f"   Size: {len(delta_bytes)} bytes")
    
    return 0


def cmd_import(args):
    """Import delta bundle."""
    path = Path(args.path)
    delta_file = Path(args.delta)
    
    if not (path / "events" / "events.ndjson").exists():
        print(f"Error: Vault not found at {path}", file=sys.stderr)
        return 1
    if not delta_file.exists():
        print(f"Error: Delta file not found: {delta_file}", file=sys.stderr)
        return 1
    
    print(f"Importing delta into: {path}")
    print(f"  From: {delta_file}")
    
    delta_bytes = delta_file.read_bytes()
    result = import_delta(path, delta_bytes)
    
    if not result.success:
        print("\n❌ Import failed:", file=sys.stderr)
        for error in result.errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    
    print(f"\n✅ Import complete!")
    print(f"   Imported: {result.imported_count} events")
    print(f"   Rejected: {result.rejected_count} events")
    print(f"   New state hash: {result.new_state_hash}")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Provara Protocol CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # init
    p_init = subparsers.add_parser("init", help="Create a new vault")
    p_init.add_argument("path", help="Path to create vault")
    p_init.add_argument("--actor", default="sovereign_genesis", help="Actor name")
    p_init.add_argument("--quorum", action="store_true", help="Generate quorum keypair")
    
    # verify
    p_verify = subparsers.add_parser("verify", help="Verify vault integrity")
    p_verify.add_argument("path", help="Path to vault")
    
    # state
    p_state = subparsers.add_parser("state", help="Show vault state")
    p_state.add_argument("path", help="Path to vault")
    p_state.add_argument("--json", action="store_true", help="Output full state as JSON")
    
    # sync
    p_sync = subparsers.add_parser("sync", help="Sync two vaults")
    p_sync.add_argument("local", help="Path to local vault")
    p_sync.add_argument("remote", help="Path to remote vault")
    
    # export
    p_export = subparsers.add_parser("export", help="Export delta bundle")
    p_export.add_argument("path", help="Path to vault")
    p_export.add_argument("--output", required=True, help="Output file path")
    p_export.add_argument("--since", help="Export events after this hash")
    
    # import
    p_import = subparsers.add_parser("import", help="Import delta bundle")
    p_import.add_argument("path", help="Path to vault")
    p_import.add_argument("--delta", required=True, help="Delta file to import")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == "init":
        return cmd_init(args)
    elif args.command == "verify":
        return cmd_verify(args)
    elif args.command == "state":
        return cmd_state(args)
    elif args.command == "sync":
        return cmd_sync(args)
    elif args.command == "export":
        return cmd_export(args)
    elif args.command == "import":
        return cmd_import(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
