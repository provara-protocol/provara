# `sync_v0`

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

## Functions

### `iter_events(path: Path) -> Iterable[Dict[str, Any]]`

Generator that yields events from an NDJSON file. 
Skips blank lines and malformed JSON.

### `load_events(path: Path) -> List[Dict[str, Any]]`

Load all events from an NDJSON file into a list.
Deprecated for large logs; use iter_events instead.

### `write_events(path: Path, events: List[Dict[str, Any]]) -> None`

Write events as NDJSON (one canonical JSON line per event).

Args:
    path: Path to write to.
    events: List of event dicts to write.

### `merge_event_logs(local_log_path: Path, remote_log_path: Path) -> MergeResult`

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

### `verify_causal_chain(events: List[Dict[str, Any]], actor_id: str) -> bool`

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

### `detect_forks(events: List[Dict[str, Any]]) -> List[Fork]`

Detect causal forks: cases where two events by the same actor
share the same prev_event_hash.

A fork indicates that an actor produced divergent histories,
typically from concurrent offline operation on multiple devices.

Args:
    events: Full event log.

Returns:
    List of Fork objects describing each fork point.

### `create_fencing_token(backpack_path: Path, private_key_b64: str, key_id: str) -> str`

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

### `validate_fencing_token(token_json: str, backpack_path: Path) -> bool`

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

### `sync_backpacks(local_path: Path, remote_path: Path, strategy: str = 'union', private_key: Optional[Ed25519PrivateKey] = None, key_id: Optional[str] = None) -> SyncResult`

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

### `export_delta(backpack_path: Path, since_hash: Optional[str] = None) -> bytes`

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

### `import_delta(backpack_path: Path, delta_bytes: bytes) -> ImportResult`

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

### `get_all_actors(events: List[Dict[str, Any]]) -> Set[str]`

Extract the set of all unique actor IDs from an event log.

### `verify_all_causal_chains(events: List[Dict[str, Any]]) -> Dict[str, bool]`

Verify causal chains for all actors in the event log.

Returns:
    Dict mapping actor_id to chain validity (True/False).

### `verify_all_signatures(events: List[Dict[str, Any]], keys_registry: Dict[str, Dict[str, Any]]) -> Tuple[int, int, List[str]]`

Verify signatures on all events.

Args:
    events: List of events to verify.
    keys_registry: Key registry (from load_keys_registry).

Returns:
    Tuple of (valid_count, invalid_count, error_messages).

### `main() -> None`

Entry point for the standalone sync CLI.

Parses subcommands (``merge``, ``delta-export``, ``delta-import``,
``check-forks``) and exits with process status code from the selected
command handler.

## Classes

### `Fork`

Represents a causal fork: two events by the same actor share prev_event_hash.

#### `Fork.to_dict(self) -> Dict[str, Any]`

No docstring provided.

### `MergeResult`

Result of merging two event logs.

#### `MergeResult.to_dict(self) -> Dict[str, Any]`

No docstring provided.

### `SyncResult`

Result of a full backpack sync operation.

#### `SyncResult.to_dict(self) -> Dict[str, Any]`

No docstring provided.

### `ImportResult`

Result of importing a delta bundle into a backpack.

#### `ImportResult.to_dict(self) -> Dict[str, Any]`

No docstring provided.
