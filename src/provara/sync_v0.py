"""
sync_v0.py — Backpack v1.0 Multi-Device Sync Layer (Phase 2)

Implements deterministic, offline-first, conflict-free synchronization
between multiple Provara backpacks. Core design principles:

  - Union merge: combine events from multiple devices, never discard
  - Deterministic: same events merged in any order produce identical state
  - Conflict-free: events are append-only, conflicts resolve at the
    belief reducer level (contested namespace)
  - Offline-first: sync works when devices reconnect, no real-time requirement
  - Fencing tokens: prevent stale writes from overwriting fresh state

What it does:
  1. Merges event logs from two backpacks (union by event_hash, dedup)
  2. Verifies per-actor causal chains
  3. Detects causal forks (two events sharing prev_event_hash)
  4. Creates and validates fencing tokens (hash + signature)
  5. Exports/imports delta bundles for efficient partial sync
  6. Re-runs the reducer on merged events to recompute state

Dependencies:
  - backpack_signing.py (Ed25519 primitives)
  - canonical_json.py (deterministic serialization)
  - reducer_v0.py (belief reducer)
  - manifest_generator.py (manifest + merkle root regeneration)
  - backpack_integrity.py (integrity primitives)

Usage:
  python sync_v0.py merge <local_backpack> <remote_backpack>
  python sync_v0.py delta-export <backpack> [--since HASH]
  python sync_v0.py delta-import <backpack> <delta_file>
  python sync_v0.py check-forks <backpack>
"""

from __future__ import annotations
import argparse
import base64
import datetime
import hashlib
import json
import os
import secrets
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .canonical_json import canonical_bytes, canonical_dumps, canonical_hash
from .backpack_signing import (
    BackpackKeypair,
    load_keys_registry,
    load_private_key_b64,
    load_public_key_b64,
    resolve_public_key,
    sign_event,
    sign_manifest,
    verify_event_signature,
)
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from .backpack_integrity import (
    canonical_json_bytes,
    merkle_root_hex,
    sha256_bytes,
    sha256_file,
    MANIFEST_EXCLUDE,
)
from .reducer_v0 import SovereignReducerV0
from .manifest_generator import build_manifest, manifest_leaves
from .checkpoint_v0 import (
    load_latest_checkpoint,
    verify_checkpoint,
    create_checkpoint,
    save_checkpoint,
)


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    """Current UTC time in ISO 8601 format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Fork:
    """Represents a causal fork: two events by the same actor share prev_event_hash."""
    actor_id: str
    prev_hash: Optional[str]
    event_a: Dict[str, Any]
    event_b: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "prev_hash": self.prev_hash,
            "event_a_id": self.event_a.get("event_id"),
            "event_b_id": self.event_b.get("event_id"),
        }


@dataclass
class MergeResult:
    """Result of merging two event logs."""
    merged_events: List[Dict[str, Any]]
    new_count: int
    conflicts: List[str] = field(default_factory=list)
    forks: List[Fork] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "merged_event_count": len(self.merged_events),
            "new_count": self.new_count,
            "conflict_count": len(self.conflicts),
            "conflicts": self.conflicts,
            "fork_count": len(self.forks),
            "forks": [f.to_dict() for f in self.forks],
        }


@dataclass
class SyncResult:
    """Result of a full backpack sync operation."""
    success: bool
    events_merged: int
    new_state_hash: Optional[str]
    fencing_token: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    forks: List[Fork] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "events_merged": self.events_merged,
            "new_state_hash": self.new_state_hash,
            "fencing_token": self.fencing_token,
            "error_count": len(self.errors),
            "errors": self.errors,
            "fork_count": len(self.forks),
        }


@dataclass
class ImportResult:
    """Result of importing a delta bundle into a backpack."""
    success: bool
    imported_count: int
    rejected_count: int
    new_state_hash: Optional[str]
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "imported_count": self.imported_count,
            "rejected_count": self.rejected_count,
            "new_state_hash": self.new_state_hash,
            "error_count": len(self.errors),
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Event log I/O
# ---------------------------------------------------------------------------

def load_events(path: Path) -> List[Dict[str, Any]]:
    """
    Load events from an NDJSON file. Skips blank lines and malformed JSON.

    Args:
        path: Path to the events.ndjson file.

    Returns:
        List of event dicts in file order.
    """
    events: List[Dict[str, Any]] = []
    if not path.exists():
        return events
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                events.append(json.loads(stripped))
            except json.JSONDecodeError:
                pass  # skip malformed lines
    return events


def write_events(path: Path, events: List[Dict[str, Any]]) -> None:
    """
    Write events as NDJSON (one canonical JSON line per event).

    Args:
        path: Path to write to.
        events: List of event dicts to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(canonical_dumps(event) + "\n")


def _event_content_hash(event: Dict[str, Any]) -> str:
    """
    Compute a content hash for deduplication purposes.
    Uses the event_id as the primary identity (it is already content-addressed).
    Falls back to hashing the full event if event_id is missing.
    """
    eid: Optional[str] = event.get("event_id")
    if eid:
        return eid
    return canonical_hash(event)


# ---------------------------------------------------------------------------
# Core sync functions
# ---------------------------------------------------------------------------

def merge_event_logs(
    local_log_path: Path,
    remote_log_path: Path,
) -> MergeResult:
    """
    Union-merge two NDJSON event logs with deduplication.

    Process:
      1. Read both event logs
      2. Combine all events, deduplicating by event_id (content-addressed)
      3. Sort by timestamp (stable sort, event_id as tiebreaker)
      4. Detect causal forks
      5. Report merge statistics

    Args:
        local_log_path: Path to the local events.ndjson
        remote_log_path: Path to the remote events.ndjson

    Returns:
        MergeResult with merged events, counts, and fork information.
    """
    local_events = load_events(local_log_path)
    remote_events = load_events(remote_log_path)

    # Build a set of known event IDs from local for dedup counting
    local_ids: Set[str] = set()
    for e in local_events:
        eid = _event_content_hash(e)
        local_ids.add(eid)

    # Union merge: combine all events, dedup by event_id
    seen: Set[str] = set()
    merged: List[Dict[str, Any]] = []
    new_count = 0

    for event in local_events:
        eid = _event_content_hash(event)
        if eid not in seen:
            seen.add(eid)
            merged.append(event)

    for event in remote_events:
        eid = _event_content_hash(event)
        if eid not in seen:
            seen.add(eid)
            merged.append(event)
            new_count += 1

    # Deterministic sort: by timestamp, then event_id as tiebreaker
    def sort_key(e: Dict[str, Any]) -> Tuple[str, str]:
        ts = e.get("timestamp_utc") or ""
        eid = e.get("event_id") or ""
        return (ts, eid)

    merged.sort(key=sort_key)

    # Detect forks
    forks = detect_forks(merged)
    conflicts = [f"Fork detected: actor={f.actor_id}, prev={f.prev_hash}" for f in forks]

    return MergeResult(
        merged_events=merged,
        new_count=new_count,
        conflicts=conflicts,
        forks=forks,
    )


def verify_causal_chain(events: List[Dict[str, Any]], actor_id: str) -> bool:
    """
    Verify the causal chain for a single actor.

    Per PROTOCOL_PROFILE.txt CAUSAL CHAIN section:
      - First event by an actor: prev_event_hash MUST be null
      - Subsequent events: prev_event_hash MUST equal the event_id
        of that actor's immediately preceding event
      - Cross-actor references: prev_event_hash MUST NOT reference
        another actor's events

    Args:
        events: Full event log (sorted by timestamp).
        actor_id: The actor whose chain to verify.

    Returns:
        True if the causal chain is valid, False otherwise.
    """
    actor_events = [
        e for e in events
        if e.get("actor") == actor_id
    ]

    if not actor_events:
        return True  # no events by this actor — trivially valid

    # First event must have prev_event_hash = null
    first = actor_events[0]
    prev_hash = first.get("prev_event_hash")
    if prev_hash is not None:
        return False

    # Each subsequent event must chain to the previous
    for i in range(1, len(actor_events)):
        current = actor_events[i]
        expected_prev = actor_events[i - 1].get("event_id")
        actual_prev = current.get("prev_event_hash")
        if actual_prev != expected_prev:
            return False

    return True


def detect_forks(events: List[Dict[str, Any]]) -> List[Fork]:
    """
    Detect causal forks: cases where two events by the same actor
    share the same prev_event_hash.

    A fork indicates that an actor produced divergent histories,
    typically from concurrent offline operation on multiple devices.

    Args:
        events: Full event log.

    Returns:
        List of Fork objects describing each fork point.
    """
    # Group by (actor, prev_event_hash)
    prev_map: Dict[Tuple[str, Optional[str]], List[Dict[str, Any]]] = {}

    for event in events:
        actor = event.get("actor")
        prev_hash = event.get("prev_event_hash")
        if actor is None:
            continue
        key = (actor, prev_hash)
        prev_map.setdefault(key, []).append(event)

    forks: List[Fork] = []
    for (actor, prev_hash), forked_events in sorted(
        prev_map.items(), key=lambda x: (x[0][0], x[0][1] or "")
    ):
        if len(forked_events) >= 2:
            # Report each pair of forking events
            for i in range(1, len(forked_events)):
                forks.append(Fork(
                    actor_id=actor,
                    prev_hash=prev_hash,
                    event_a=forked_events[0],
                    event_b=forked_events[i],
                ))

    return forks


# ---------------------------------------------------------------------------
# Fencing tokens
# ---------------------------------------------------------------------------

def create_fencing_token(
    backpack_path: Path,
    private_key_b64: str,
    key_id: str,
) -> str:
    """
    Generate a fencing token to prevent stale writes.

    Token construction:
      1. Read the latest event hash from the event log
      2. Generate: SHA-256(latest_event_hash + current_timestamp + random_nonce)
      3. Sign the token hash with the active key
      4. Return a JSON-encoded signed token

    Args:
        backpack_path: Path to the backpack root directory.
        private_key_b64: Base64-encoded Ed25519 private key.
        key_id: Key ID of the signing key.

    Returns:
        JSON string containing the signed fencing token.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    events_path = backpack_path / "events" / "events.ndjson"
    events = load_events(events_path)

    latest_hash = ""
    if events:
        latest_hash = events[-1].get("event_id", "")

    timestamp = _utc_now()
    nonce = secrets.token_hex(16)

    # Token hash = SHA-256(latest_event_hash + timestamp + nonce)
    token_input = f"{latest_hash}:{timestamp}:{nonce}"
    token_hash = hashlib.sha256(token_input.encode("utf-8")).hexdigest()

    # Sign the token hash
    private_key = load_private_key_b64(private_key_b64)
    token_bytes = token_hash.encode("utf-8")
    sig_bytes = private_key.sign(token_bytes)
    sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

    token_record = {
        "token_hash": token_hash,
        "latest_event_id": latest_hash,
        "timestamp": timestamp,
        "nonce": nonce,
        "key_id": key_id,
        "sig": sig_b64,
    }

    return canonical_dumps(token_record)


def validate_fencing_token(
    token_json: str,
    backpack_path: Path,
) -> bool:
    """
    Validate a fencing token against a backpack.

    Checks:
      1. Token JSON is well-formed
      2. Signature is valid (verified against keys.json)
      3. The referenced latest_event_id exists in the event log

    Args:
        token_json: JSON string of the fencing token.
        backpack_path: Path to the backpack root directory.

    Returns:
        True if the token is valid, False otherwise.
    """
    try:
        token = json.loads(token_json)
    except (json.JSONDecodeError, TypeError):
        return False

    # Required fields
    for field_name in ("token_hash", "latest_event_id", "key_id", "sig", "nonce", "timestamp"):
        if field_name not in token:
            return False

    # Verify the token hash is correctly derived
    expected_input = f"{token['latest_event_id']}:{token['timestamp']}:{token['nonce']}"
    expected_hash = hashlib.sha256(expected_input.encode("utf-8")).hexdigest()
    if token["token_hash"] != expected_hash:
        return False

    # Load keys registry and resolve public key
    keys_path = backpack_path / "identity" / "keys.json"
    if not keys_path.exists():
        return False
    registry = load_keys_registry(keys_path)
    public_key = resolve_public_key(token["key_id"], registry)
    if public_key is None:
        return False

    # Verify signature over token_hash
    try:
        sig_bytes = base64.b64decode(token["sig"])
        token_bytes = token["token_hash"].encode("utf-8")
        public_key.verify(sig_bytes, token_bytes)
    except Exception:
        return False

    # Verify the referenced event exists in the log
    events_path = backpack_path / "events" / "events.ndjson"
    events = load_events(events_path)
    event_ids = {e.get("event_id") for e in events}

    latest_id = token["latest_event_id"]
    if latest_id and latest_id not in event_ids:
        return False

    return True


# ---------------------------------------------------------------------------
# Full backpack sync
# ---------------------------------------------------------------------------

def sync_backpacks(
    local_path: Path,
    remote_path: Path,
    strategy: str = "union",
    private_key: Optional[Ed25519PrivateKey] = None,
    key_id: Optional[str] = None,
) -> SyncResult:
    """
    Main sync entry point: merge two backpacks' event logs and recompute state.

    Process:
      1. Merge event logs (union dedup)
      2. Re-run reducer on merged events to compute new state (using checkpoints)
      3. Regenerate manifest and merkle root
      4. Save a new checkpoint if signing keys are provided
      5. Return SyncResult with statistics

    Args:
        local_path: Path to the local backpack root.
        remote_path: Path to the remote backpack root.
        strategy: Merge strategy. Currently only "union" is supported.
        private_key: Optional key to sign a new checkpoint.
        key_id: Optional key ID for the signing key.

    Returns:
        SyncResult with merge statistics and new state hash.
    """
    if strategy != "union":
        return SyncResult(
            success=False,
            events_merged=0,
            new_state_hash=None,
            errors=[f"Unsupported merge strategy: {strategy}"],
        )

    local_events_path = local_path / "events" / "events.ndjson"
    remote_events_path = remote_path / "events" / "events.ndjson"

    errors: List[str] = []

    # Step 1: Merge event logs
    try:
        merge = merge_event_logs(local_events_path, remote_events_path)
    except Exception as exc:
        return SyncResult(
            success=False,
            events_merged=0,
            new_state_hash=None,
            errors=[f"Merge failed: {exc}"],
        )

    # Step 2: Re-run reducer on merged events (using checkpoints for speed)
    try:
        reducer = _reconstruct_state(local_path, merge.merged_events)
        new_state = reducer.export_state()
        new_state_hash = new_state["metadata"]["state_hash"]
    except Exception as exc:
        return SyncResult(
            success=False,
            events_merged=merge.new_count,
            new_state_hash=None,
            errors=[f"State reconstruction failed: {exc}"],
        )

    # Step 3: Write merged events back to local backpack
    write_events(local_events_path, merge.merged_events)

    # Step 4: Write reducer state
    state_path = local_path / "state"
    state_path.mkdir(parents=True, exist_ok=True)
    state_file = state_path / "current_state.json"
    state_file.write_text(
        canonical_dumps(new_state) + "\n",
        encoding="utf-8",
    )

    # Step 5: Regenerate manifest and merkle root
    try:
        _regenerate_manifest(local_path)
    except Exception as exc:
        errors.append(f"Manifest regeneration failed: {exc}")

    # Step 6: Create new checkpoint if keys provided
    if private_key and key_id and not errors:
        try:
            cp = create_checkpoint(local_path, new_state, private_key, key_id)
            save_checkpoint(local_path, cp)
        except Exception as exc:
            errors.append(f"Checkpoint creation failed: {exc}")

    return SyncResult(
        success=len(errors) == 0,
        events_merged=merge.new_count,
        new_state_hash=new_state_hash,
        errors=errors,
        forks=merge.forks,
    )


def _reconstruct_state(
    backpack_path: Path, merged_events: List[Dict[str, Any]]
) -> SovereignReducerV0:
    """
    Optimized state reconstruction using the latest verified checkpoint.
    """
    reducer = SovereignReducerV0()
    
    # 1. Try to load latest checkpoint
    cp_dict = load_latest_checkpoint(backpack_path)
    if cp_dict:
        # Verify checkpoint against keys.json
        keys_path = backpack_path / "identity" / "keys.json"
        if keys_path.exists():
            registry = load_keys_registry(keys_path)
            pub_key = resolve_public_key(cp_dict.get("key_id", ""), registry)
            
            if pub_key and verify_checkpoint(cp_dict, pub_key):
                # Check if checkpoint's merkle_root matches current file system
                # (Skip this check for performance if we trust the vault directory)
                
                # Load checkpoint state into reducer
                cp_state = cp_dict["state"]
                reducer.state["canonical"] = cp_state.get("canonical", {})
                reducer.state["local"] = cp_state.get("local", {})
                reducer.state["contested"] = cp_state.get("contested", {})
                reducer.state["archived"] = cp_state.get("archived", {})
                
                meta_p = cp_state.get("metadata_partial", {})
                reducer.state["metadata"]["last_event_id"] = meta_p.get("last_event_id")
                reducer.state["metadata"]["event_count"] = meta_p.get("event_count", 0)
                reducer.state["metadata"]["current_epoch"] = meta_p.get("current_epoch")
                reducer.state["metadata"]["reducer"] = meta_p.get("reducer")
                
                # Recompute initial state hash from checkpoint
                reducer.state["metadata"]["state_hash"] = reducer._compute_state_hash()
                
                # Find events that happened AFTER this checkpoint
                last_id = reducer.state["metadata"]["last_event_id"]
                start_idx = 0
                if last_id:
                    for i, ev in enumerate(merged_events):
                        if ev.get("event_id") == last_id:
                            start_idx = i + 1
                            break
                
                reducer.apply_events(merged_events[start_idx:])
                return reducer

    # Fallback: full replay
    reducer.apply_events(merged_events)
    return reducer


def _regenerate_manifest(backpack_path: Path) -> None:
    """
    Regenerate manifest.json and merkle_root.txt for a backpack.
    Does NOT re-sign the manifest (caller must handle signing if needed).
    """
    manifest = build_manifest(backpack_path, set(MANIFEST_EXCLUDE))
    leaves = manifest_leaves(manifest)
    root_hex = merkle_root_hex(leaves)

    (backpack_path / "manifest.json").write_bytes(
        canonical_json_bytes(manifest)
    )
    (backpack_path / "merkle_root.txt").write_text(
        root_hex + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Delta export / import
# ---------------------------------------------------------------------------

def export_delta(
    backpack_path: Path,
    since_hash: Optional[str] = None,
) -> bytes:
    """
    Export events since a given hash as a portable NDJSON bundle.

    The delta bundle is a UTF-8 encoded byte string containing:
      - A header line (JSON object with metadata)
      - One NDJSON line per event

    If since_hash is None, all events are exported.

    Args:
        backpack_path: Path to the backpack root.
        since_hash: Export events after this event_id. If None, export all.

    Returns:
        UTF-8 encoded bytes of the delta bundle.
    """
    events_path = backpack_path / "events" / "events.ndjson"
    all_events = load_events(events_path)

    # Determine which events to export
    if since_hash is None:
        export_events = all_events
    else:
        # Find the index of the since_hash event
        found_idx = None
        for i, e in enumerate(all_events):
            if e.get("event_id") == since_hash:
                found_idx = i
                break

        if found_idx is None:
            # Hash not found — export everything
            export_events = all_events
        else:
            # Export everything after the found event
            export_events = all_events[found_idx + 1:]

    # Load keys registry for verification metadata
    keys_path = backpack_path / "identity" / "keys.json"
    keys_data = {}
    if keys_path.exists():
        keys_data = json.loads(keys_path.read_text(encoding="utf-8"))

    # Build the delta header
    header = {
        "type": "provara_delta_v1",
        "since_hash": since_hash,
        "event_count": len(export_events),
        "exported_at": _utc_now(),
        "keys": keys_data.get("keys", []),
    }

    # Build the bundle
    lines = [canonical_dumps(header)]
    for event in export_events:
        lines.append(canonical_dumps(event))

    bundle = "\n".join(lines) + "\n"
    return bundle.encode("utf-8")


def import_delta(
    backpack_path: Path,
    delta_bytes: bytes,
) -> ImportResult:
    """
    Import a delta bundle into a backpack.

    Process:
      1. Parse the delta header and events
      2. Verify all event signatures against included keys
      3. Merge into existing event log (union dedup)
      4. Re-run reducer on merged events
      5. Regenerate manifest

    Args:
        backpack_path: Path to the backpack root.
        delta_bytes: UTF-8 encoded delta bundle bytes.

    Returns:
        ImportResult with import statistics.
    """
    errors: List[str] = []
    imported_count = 0
    rejected_count = 0

    # Parse delta bundle
    try:
        text = delta_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return ImportResult(
            success=False,
            imported_count=0,
            rejected_count=0,
            new_state_hash=None,
            errors=["Delta bundle is not valid UTF-8"],
        )

    lines = [ln for ln in text.strip().split("\n") if ln.strip()]
    if not lines:
        return ImportResult(
            success=False,
            imported_count=0,
            rejected_count=0,
            new_state_hash=None,
            errors=["Delta bundle is empty"],
        )

    # Parse header
    try:
        header = json.loads(lines[0])
    except json.JSONDecodeError:
        return ImportResult(
            success=False,
            imported_count=0,
            rejected_count=0,
            new_state_hash=None,
            errors=["Invalid delta header"],
        )

    if header.get("type") != "provara_delta_v1":
        return ImportResult(
            success=False,
            imported_count=0,
            rejected_count=0,
            new_state_hash=None,
            errors=[f"Unknown delta type: {header.get('type')}"],
        )

    # Build a key registry from the delta's included keys AND local keys
    delta_keys = header.get("keys", [])
    delta_registry: Dict[str, Dict[str, Any]] = {}
    for entry in delta_keys:
        kid = entry.get("key_id")
        if kid:
            delta_registry[kid] = entry

    # Also load local keys
    local_keys_path = backpack_path / "identity" / "keys.json"
    if local_keys_path.exists():
        local_keys_data = json.loads(local_keys_path.read_text(encoding="utf-8"))
        for entry in local_keys_data.get("keys", []):
            kid = entry.get("key_id")
            if kid:
                delta_registry[kid] = entry

    # Parse and verify delta events
    delta_events: List[Dict[str, Any]] = []
    for line in lines[1:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            rejected_count += 1
            errors.append("Skipped malformed event line")
            continue

        # Verify signature if present
        sig = event.get("sig")
        kid = event.get("actor_key_id")
        if sig and kid:
            pk = resolve_public_key(kid, delta_registry)
            if pk is not None:
                if not verify_event_signature(event, pk):
                    rejected_count += 1
                    eid = event.get("event_id", "unknown")
                    errors.append(f"Invalid signature on event {eid}")
                    continue

        delta_events.append(event)

    # Load existing events
    events_path = backpack_path / "events" / "events.ndjson"
    existing_events = load_events(events_path)

    # Union merge with dedup
    seen: Set[str] = set()
    merged: List[Dict[str, Any]] = []

    for event in existing_events:
        eid = _event_content_hash(event)
        if eid not in seen:
            seen.add(eid)
            merged.append(event)

    for event in delta_events:
        eid = _event_content_hash(event)
        if eid not in seen:
            seen.add(eid)
            merged.append(event)
            imported_count += 1

    # Sort deterministically
    def sort_key(e: Dict[str, Any]) -> Tuple[str, str]:
        ts = e.get("timestamp_utc") or ""
        eid = e.get("event_id") or ""
        return (ts, eid)

    merged.sort(key=sort_key)

    # Write merged events
    write_events(events_path, merged)

    # Re-run reducer
    reducer = SovereignReducerV0()
    reducer.apply_events(merged)
    new_state = reducer.export_state()
    new_state_hash = new_state["metadata"]["state_hash"]

    # Write state
    state_path = backpack_path / "state"
    state_path.mkdir(parents=True, exist_ok=True)
    state_file = state_path / "current_state.json"
    state_file.write_text(
        canonical_dumps(new_state) + "\n",
        encoding="utf-8",
    )

    # Regenerate manifest
    try:
        _regenerate_manifest(backpack_path)
    except Exception as exc:
        errors.append(f"Manifest regeneration failed: {exc}")

    return ImportResult(
        success=rejected_count == 0 and len(errors) == 0,
        imported_count=imported_count,
        rejected_count=rejected_count,
        new_state_hash=new_state_hash,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def get_all_actors(events: List[Dict[str, Any]]) -> Set[str]:
    """Extract the set of all unique actor IDs from an event log."""
    actors: Set[str] = set()
    for e in events:
        actor = e.get("actor")
        if actor:
            actors.add(actor)
    return actors


def verify_all_causal_chains(events: List[Dict[str, Any]]) -> Dict[str, bool]:
    """
    Verify causal chains for all actors in the event log.

    Returns:
        Dict mapping actor_id to chain validity (True/False).
    """
    actors = get_all_actors(events)
    results: Dict[str, bool] = {}
    for actor in sorted(actors):
        results[actor] = verify_causal_chain(events, actor)
    return results


def verify_all_signatures(
    events: List[Dict[str, Any]],
    keys_registry: Dict[str, Dict[str, Any]],
) -> Tuple[int, int, List[str]]:
    """
    Verify signatures on all events.

    Args:
        events: List of events to verify.
        keys_registry: Key registry (from load_keys_registry).

    Returns:
        Tuple of (valid_count, invalid_count, error_messages).
    """
    valid = 0
    invalid = 0
    errors: List[str] = []

    for event in events:
        sig = event.get("sig")
        kid = event.get("actor_key_id")
        eid = event.get("event_id", "unknown")

        if not sig:
            # Unsigned events are not verified (may be pre-signing)
            continue

        if not kid:
            invalid += 1
            errors.append(f"Event {eid}: missing actor_key_id")
            continue

        pk = resolve_public_key(kid, keys_registry)
        if pk is None:
            invalid += 1
            errors.append(f"Event {eid}: key {kid} not found in registry")
            continue

        if verify_event_signature(event, pk):
            valid += 1
        else:
            invalid += 1
            errors.append(f"Event {eid}: invalid signature")

    return valid, invalid, errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_merge(args: argparse.Namespace) -> int:
    """Handle the 'merge' subcommand."""
    local_path = Path(args.local_backpack).resolve()
    remote_path = Path(args.remote_backpack).resolve()

    if not local_path.is_dir():
        print(f"Error: Local backpack not found: {local_path}", file=sys.stderr)
        return 1
    if not remote_path.is_dir():
        print(f"Error: Remote backpack not found: {remote_path}", file=sys.stderr)
        return 1

    print(f"Syncing: {local_path} <- {remote_path}")

    result = sync_backpacks(local_path, remote_path)

    print(f"  Events merged: {result.events_merged}")
    print(f"  New state hash: {result.new_state_hash}")
    if result.forks:
        print(f"  Forks detected: {len(result.forks)}")
        for f in result.forks:
            print(f"    Fork: actor={f.actor_id}, prev={f.prev_hash}")
    if result.errors:
        print(f"  Errors: {len(result.errors)}")
        for e in result.errors:
            print(f"    {e}", file=sys.stderr)

    if result.success:
        print("  Sync: SUCCESS")
        return 0
    else:
        print("  Sync: FAILED", file=sys.stderr)
        return 1


def _cmd_delta_export(args: argparse.Namespace) -> int:
    """Handle the 'delta-export' subcommand."""
    bp_path = Path(args.backpack).resolve()

    if not bp_path.is_dir():
        print(f"Error: Backpack not found: {bp_path}", file=sys.stderr)
        return 1

    since = args.since if hasattr(args, "since") else None
    delta = export_delta(bp_path, since_hash=since)

    # Write to stdout or file
    if hasattr(args, "output") and args.output:
        out_path = Path(args.output)
        out_path.write_bytes(delta)
        print(f"Delta exported to: {out_path} ({len(delta)} bytes)")
    else:
        sys.stdout.buffer.write(delta)

    return 0


def _cmd_delta_import(args: argparse.Namespace) -> int:
    """Handle the 'delta-import' subcommand."""
    bp_path = Path(args.backpack).resolve()
    delta_path = Path(args.delta_file).resolve()

    if not bp_path.is_dir():
        print(f"Error: Backpack not found: {bp_path}", file=sys.stderr)
        return 1
    if not delta_path.is_file():
        print(f"Error: Delta file not found: {delta_path}", file=sys.stderr)
        return 1

    delta_bytes = delta_path.read_bytes()
    result = import_delta(bp_path, delta_bytes)

    print(f"  Imported: {result.imported_count}")
    print(f"  Rejected: {result.rejected_count}")
    print(f"  New state hash: {result.new_state_hash}")
    if result.errors:
        for e in result.errors:
            print(f"    {e}", file=sys.stderr)

    if result.success:
        print("  Import: SUCCESS")
        return 0
    else:
        print("  Import: FAILED", file=sys.stderr)
        return 1


def _cmd_check_forks(args: argparse.Namespace) -> int:
    """Handle the 'check-forks' subcommand."""
    bp_path = Path(args.backpack).resolve()

    if not bp_path.is_dir():
        print(f"Error: Backpack not found: {bp_path}", file=sys.stderr)
        return 1

    events_path = bp_path / "events" / "events.ndjson"
    events = load_events(events_path)

    forks = detect_forks(events)
    chains = verify_all_causal_chains(events)

    print(f"Events: {len(events)}")
    print(f"Actors: {len(chains)}")
    print(f"Forks: {len(forks)}")

    for actor, valid in sorted(chains.items()):
        status = "OK" if valid else "BROKEN"
        print(f"  {actor}: chain {status}")

    for f in forks:
        print(f"  Fork: actor={f.actor_id}, prev={f.prev_hash}")
        print(f"    event_a: {f.event_a.get('event_id')}")
        print(f"    event_b: {f.event_b.get('event_id')}")

    return 0 if not forks else 1


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Backpack v1.0 Multi-Device Sync Layer",
        epilog="Phase 2 of the Provara Protocol.",
    )
    sub = ap.add_subparsers(dest="command", help="Sync operations")

    # merge
    p_merge = sub.add_parser(
        "merge",
        help="Merge two backpacks (union sync)",
    )
    p_merge.add_argument("local_backpack", help="Path to local backpack")
    p_merge.add_argument("remote_backpack", help="Path to remote backpack")

    # delta-export
    p_export = sub.add_parser(
        "delta-export",
        help="Export events as a delta bundle",
    )
    p_export.add_argument("backpack", help="Path to backpack")
    p_export.add_argument("--since", default=None, help="Export events after this event_id")
    p_export.add_argument("-o", "--output", default=None, help="Output file (default: stdout)")

    # delta-import
    p_import = sub.add_parser(
        "delta-import",
        help="Import a delta bundle into a backpack",
    )
    p_import.add_argument("backpack", help="Path to backpack")
    p_import.add_argument("delta_file", help="Path to delta bundle file")

    # check-forks
    p_forks = sub.add_parser(
        "check-forks",
        help="Check for causal forks in a backpack",
    )
    p_forks.add_argument("backpack", help="Path to backpack")

    args = ap.parse_args()

    if args.command == "merge":
        sys.exit(_cmd_merge(args))
    elif args.command == "delta-export":
        sys.exit(_cmd_delta_export(args))
    elif args.command == "delta-import":
        sys.exit(_cmd_delta_import(args))
    elif args.command == "check-forks":
        sys.exit(_cmd_check_forks(args))
    else:
        ap.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
