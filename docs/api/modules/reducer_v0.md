# reducer_v0

**Module:** `src/provara/reducer_v0.py`

Deterministic belief reducer. Processes events to derive beliefs with byte-identical state hashes across all machines.

## Golden Rule

**Truth is not merged. Evidence is merged. Truth is recomputed.**

The reducer is a pure function: `f(events) -> state`. Given identical events, it always produces identical output. No heuristics, no guesses, no merge conflicts at the belief layer.

## Core Invariants

1. **Events are immutable** — Corrections are new events, not overwrites
2. **Determinism** — Same events in same order → byte-identical state hash
3. **Provenance required** — Every claim includes actor, timestamp, confidence
4. **Reducer doesn't verify** — Signature/chain verification is sync layer's job

## Four-Namespace Model

Beliefs are organized by epistemic status:

| Namespace | Meaning | Promotion |
|-----------|---------|-----------|
| `canonical/` | Institutionally attested truth | Requires ATTESTATION event |
| `local/` | Node-local observations | Auto-promotes if no conflict |
| `contested/` | Conflicting high-confidence evidence | Requires explicit RESOLUTION |
| `archived/` | Superseded canonical beliefs | Automatic on supersession |

## Event Types

### OBSERVATION

Raw observation from a sensor, actor, or AI system.

```python
event = {
    "type": "OBSERVATION",
    "subject": "family_tree",
    "predicate": "child_of",
    "value": "John",
    "confidence": 0.95,
    "namespace": "local",  # defaults to local
}
```

→ Lands in `local/`. If no conflict, auto-promotes to `canonical/` with next attestation.

### ATTESTATION

Institutional claim. Moves observation to `canonical/` or escalates conflict to `contested/`.

```python
event = {
    "type": "ATTESTATION",
    "subject": "family_tree",
    "predicate": "child_of",
    "value": "John",
    "confidence": 0.99,  # higher confidence
}
```

### RETRACTION

Removes or archives a belief. Original evidence preserved in `archived/`.

### REDUCER_EPOCH

Marks a version point. Allows checkpointing of state for fast replay.

## Core Functions

### `SovereignReducerV0`

The main reducer class.

```python
from provara.reducer_v0 import SovereignReducerV0

reducer = SovereignReducerV0()
state = reducer.apply_events([event1, event2, event3])

# state.canonical → confirmed beliefs
# state.contested → conflicting high-confidence claims
# state.state_hash → byte-identical hash of entire state
```

### `apply_events(events: List[Dict[str, Any]]) -> StateSnapshot`

Process a list of events and return final state.

```python
events = [
    {"type": "OBSERVATION", "subject": "x", "predicate": "p", "value": 1, "confidence": 0.5},
    {"type": "OBSERVATION", "subject": "x", "predicate": "p", "value": 2, "confidence": 0.6},
]

state = reducer.apply_events(events)

# state.contested["x:p"] → both values (conflicting)
# state.state_hash → deterministic SHA-256 of entire state
```

## Confidence Thresholds

- **Local promotion:** 0.5 default (configurable)
- **Conflict threshold:** 0.5 (two observations with >= 0.5 confidence conflict)
- **Agreement strength:** Max confidence retained (if two observations agree on same value, confidence increases)

## State Hash Guarantee

Two key properties:

1. **Determinism:** `state_hash(events) == state_hash(events)` always
2. **Content-addressability:** State hash changes if any event changes, added, or removed

This enables:
- Auditing: "Verify state hash matches my computation"
- Caching: "State hash is my cache key"
- Checkpointing: "Store state hash as signing anchor"

## Error Handling

Malformed events are logged but don't crash the reducer:

```python
event_malformed = {"type": "OBSERVATION"}  # missing subject

state = reducer.apply_events([event_malformed])
# Event skipped. state._ignored_types tracks what was skipped.
```

## Performance

For N events:
- **Time:** O(N) single pass
- **Space:** O(unique_beliefs) — one entry per (subject, predicate) pair
- **Typical:** 1000 events → < 10ms, < 100KB state

## Example: Family Tree Resolution

```python
from provara.reducer_v0 import SovereignReducerV0

reducer = SovereignReducerV0()

# Alice observes: Bob is John's child
event1 = {
    "type": "OBSERVATION",
    "subject": "John",
    "predicate": "child_of",
    "value": "Bob",
    "confidence": 0.90,
    "actor": "alice",
    "timestamp_utc": "2024-01-01T00:00:00Z"
}

# Carol contradicts: Bob is Frank's child
event2 = {
    "type": "OBSERVATION",
    "subject": "Frank",
    "predicate": "child_of", 
    "value": "Bob",
    "confidence": 0.85,
    "actor": "carol",
    "timestamp_utc": "2024-01-02T00:00:00Z"
}

state = reducer.apply_events([event1, event2])

# state.contested["Bob:child_of"] → [{value: "John", confidence: 0.90}, {value: "Frank", confidence: 0.85}]

# Alice issues ATTESTATION to resolve
resolution = {
    "type": "ATTESTATION",
    "subject": "John",
    "predicate": "child_of",
    "value": "Bob",
    "confidence": 0.99,
}

state2 = reducer.apply_events([event1, event2, resolution])
# state2.canonical["John:child_of"] → Bob (attested)
# state2.contested cleared (or evidence preserved)
```

## References

- [Provara Protocol: Reducer Specification](https://provara.dev/spec/)
- [Four-Namespace Model](https://provara.dev/spec/#four-namespace-model)
