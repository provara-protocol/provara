# sync_v0

**Module:** `src/provara/sync_v0.py`

Union merge with causal chain verification, fork detection, and fencing tokens. Enables safe multi-device vault synchronization.

## Golden Rule

**Truth is not merged. Evidence is merged. Truth is recomputed.**

When two vaults diverge, `sync_v0` merges their raw events (union merge), then replays the reducer to derive fresh beliefs. No heuristics, no last-write-wins.

## Core Functions

### `sync(vault_a: Path, vault_b: Path, output_path: Path) -> Dict[str, Any]`

Merge two vaults. Returns merged vault + summary of new events.

```python
from provara.sync_v0 import sync
from pathlib import Path

vault1 = Path("My_Backpack_Desktop")
vault2 = Path("My_Backpack_Phone")
merged = Path("My_Backpack_Merged")

result = sync(vault1, vault2, merged)

# result = {
#     "events_from_a": 42,
#     "events_from_b": 38,
#     "duplicates_removed": 5,
#     "new_events_in_merge": 75,
#     "state_hash": "abc123...",
#     "conflicts": [],  # or list of conflicting beliefs
# }
```

### `verify_chain(events: List[Dict[str, Any]], public_keys: Dict[str, str]) -> bool`

Verify causal chain + signatures. Returns True if all events are valid.

```python
from provara.sync_v0 import verify_chain

is_valid = verify_chain(events, public_keys_dict)

if not is_valid:
    raise ValueError("Chain verification failed!")
```

### `detect_forks(vault_path: Path) -> List[Tuple[str, List[Dict[str, Any]]]]`

Detect fork branches in a vault (same actor, diverging causal chains).

```python
from provara.sync_v0 import detect_forks

forks = detect_forks(vault_path)

if forks:
    for actor, diverged_events in forks:
        print(f"Fork detected for {actor}: {len(diverged_events)} events")
```

## Merge Algorithm

1. **Union merge** — Collect all events from both vaults
2. **Deduplication** — Remove duplicates by event_id
3. **Chain validation** — Verify each actor's causal chain
4. **Fork detection** — Flag branches (same actor, diverging chains)
5. **Reducer replay** — Re-run reducer on merged events
6. **State hash** — Compute final state_hash

Result: Two vaults → One merged vault with all evidence, no conflicts at belief layer.

## Causal Chain Invariants

For each actor:

1. **First event** has `prev_event_hash = null`
2. **Subsequent events** have `prev_event_hash = event_id` of previous event (same actor)
3. **No gaps** — If event E2 claims E1 as prev, E1 must exist
4. **No cross-actor references** — Actor A events cannot reference actor B events

Violation → chain verification fails.

## Fencing Tokens

Optional security mechanism (future extension). Prevents stale updates from old vault snapshots.

```
Vault snapshot at time T has token=V1
At time T+1, new token V2 is issued
Older events with V1 are rejected on sync
```

## Example: Multi-Device Sync

```python
from provara.sync_v0 import sync, verify_chain
from provara.backpack_integrity import compute_merkle_root
from pathlib import Path
import json

# 1. Start with vault on desktop
desktop_vault = Path("Desktop_Vault")

# 2. Copy to phone, make changes
phone_vault = Path("Phone_Vault")

# Alice adds family event on desktop
# Bob adds separate family event on phone

# 3. Sync back to desktop
merged = Path("Desktop_Vault_Merged")
result = sync(desktop_vault, phone_vault, merged)

print(f"Merged {result['events_from_a']} + {result['events_from_b']} events")
print(f"New beliefs state_hash: {result['state_hash']}")

# 4. Verify merged vault
manifest = json.loads((merged / "manifest.json").read_text())
files = [merged / f for f in manifest["files"]]
merkle_root = compute_merkle_root(files)

if merkle_root == manifest["merkle_root"]:
    print("✓ Merged vault integrity verified")
    
    # 5. Copy merged back to phone
    # (full bi-directional sync)
else:
    print("✗ Tampering detected!")
```

## Conflict Resolution

If Alice and Bob write conflicting observations on the same belief:

1. Both observations land in `contested/` namespace
2. Whoever issues the next ATTESTATION wins (or both remain contested)
3. No data loss — full history preserved in `archived/` and `contested/`

## Performance

- **Merge:** O(N) where N = total events
- **Typical:** 1000 events per vault → ~5ms merge
- **Verification:** 0.5ms per event

## References

- [Provara: Sync Specification](https://provara.dev/spec/)
- [Multi-Device Vault Sync Guide](https://provara.dev/docs/sync/)
