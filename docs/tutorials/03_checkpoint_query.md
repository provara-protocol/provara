# Tutorial 3: Checkpoint & Query

**Reading time:** 4 minutes  
**Prerequisites:** Tutorial 1 completed

Create a checkpoint for fast state recovery, then query events by actor and date range.

---

## Why Checkpoints?

Replaying a 1000-event vault from genesis is slow. Checkpoints provide:
- **Fast loading:** Jump to a known-good state
- **Cryptographic integrity:** Checkpoints are signed
- **Verification:** Validate checkpoint against event chain

---

## Step 1: Create a Vault with Multiple Events

```bash
# Initialize vault
provara init query_vault --actor "analyst" --private-keys analyst_keys.json

# Append several events
provara append query_vault \
  --type OBSERVATION \
  --data '{"subject": "metric", "predicate": "cpu", "value": 45}' \
  --keyfile analyst_keys.json --actor "analyst"

provara append query_vault \
  --type OBSERVATION \
  --data '{"subject": "metric", "predicate": "cpu", "value": 67}' \
  --keyfile analyst_keys.json --actor "analyst"

provara append query_vault \
  --type OBSERVATION \
  --data '{"subject": "metric", "predicate": "memory", "value": 2048}' \
  --keyfile analyst_keys.json --actor "analyst"
```

---

## Step 2: Create a Checkpoint

```bash
provara checkpoint query_vault --keyfile analyst_keys.json
```

**Expected output:**
```
Checkpoint saved: query_vault/checkpoints/0000000005.chk (events=5)
```

The checkpoint contains:
- Full state snapshot (all namespaces)
- Event count at checkpoint time
- Signature from checkpoint creator
- State hash for verification

---

## Step 3: Verify the Checkpoint

```bash
python -c "
from provara import Vault, load_latest_checkpoint, verify_checkpoint
from pathlib import Path

vault = Vault('query_vault')
cp = load_latest_checkpoint(vault.path)
print(f'Checkpoint events: {cp.event_count}')
print(f'Checkpoint state hash: {cp.state_hash}')

# Verify against current state
current_state = vault.replay_state()
is_valid = verify_checkpoint(vault.path, cp)
print(f'Checkpoint valid: {is_valid}')
"
```

---

## Step 4: Query Events by Actor

Use Python to query events:

```python
from provara import Vault
from pathlib import Path

vault = Vault('query_vault')
events_file = vault.path / 'events' / 'events.ndjson'

# Load and filter events
import json
events = []
with open(events_file) as f:
    for line in f:
        events.append(json.loads(line))

# Filter by actor
analyst_events = [e for e in events if e.get('actor') == 'analyst']
print(f"Events by analyst: {len(analyst_events)}")

# Filter by type
observations = [e for e in events if e.get('type') == 'OBSERVATION']
print(f"Observations: {len(observations)}")
```

---

## Step 5: Query by Date Range

```python
from datetime import datetime, timezone

# Parse timestamps
def parse_ts(ts_str):
    return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))

# Query: events between two dates
start = datetime(2026, 2, 18, 0, 0, 0, tzinfo=timezone.utc)
end = datetime(2026, 2, 18, 23, 59, 59, tzinfo=timezone.utc)

filtered = [
    e for e in events
    if start <= parse_ts(e['timestamp_utc']) <= end
]

print(f"Events on 2026-02-18: {len(filtered)}")
```

---

## Step 6: Query by Subject/Predicate

```python
# Query: all CPU metrics
cpu_events = [
    e for e in events
    if e.get('payload', {}).get('subject') == 'metric'
    and e.get('payload', {}).get('predicate') == 'cpu'
]

for e in cpu_events:
    value = e['payload']['value']
    print(f"CPU: {value}")
```

---

## Step 7: Build a Query Helper (Optional)

Create a reusable query module:

```python
# query_helpers.py
from provara import Vault
from datetime import datetime
from typing import Optional, List, Dict, Any

class VaultQuerier:
    def __init__(self, vault_path: str):
        self.vault = Vault(vault_path)
        self.events_file = self.vault.path / 'events' / 'events.ndjson'
    
    def _load_events(self) -> List[Dict[str, Any]]:
        events = []
        with open(self.events_file) as f:
            for line in f:
                events.append(json.loads(line))
        return events
    
    def by_actor(self, actor: str) -> List[Dict]:
        events = self._load_events()
        return [e for e in events if e.get('actor') == actor]
    
    def by_type(self, event_type: str) -> List[Dict]:
        events = self._load_events()
        return [e for e in events if e.get('type') == event_type]
    
    def by_date_range(self, start: datetime, end: datetime) -> List[Dict]:
        events = self._load_events()
        return [
            e for e in events
            if start <= datetime.fromisoformat(e['timestamp_utc'].replace('Z', '+00:00')) <= end
        ]
    
    def by_subject_predicate(self, subject: str, predicate: str) -> List[Dict]:
        events = self._load_events()
        return [
            e for e in events
            if e.get('payload', {}).get('subject') == subject
            and e.get('payload', {}).get('predicate') == predicate
        ]

# Usage
querier = VaultQuerier('query_vault')
cpu_metrics = querier.by_subject_predicate('metric', 'cpu')
```

---

## Checkpoint File Format

Checkpoints are stored as NDJSON:

```
query_vault/checkpoints/
├── 0000000003.chk    # Checkpoint at event 3
├── 0000000007.chk    # Checkpoint at event 7
└── ...
```

Each checkpoint file:
```json
{"event_count": 5, "state_hash": "...", "state": {...}, "sig": "...", "signer_key_id": "bp1_..."}
```

---

## Performance Tips

| Vault Size | Without Checkpoint | With Checkpoint |
|------------|-------------------|-----------------|
| 100 events | ~50ms | ~5ms |
| 1,000 events | ~500ms | ~50ms |
| 10,000 events | ~5s | ~100ms |

**Best practices:**
- Create checkpoints every 100-1000 events
- Keep last 10 checkpoints (delete older ones)
- Verify checkpoints before trusting them

---

## Next Steps

- **Tutorial 4:** MCP Integration — connect Provara vault to an AI agent via MCP server
- **Tutorial 5:** Anchor to L2 — timestamp or anchor vault state to external trust anchor

---

**Reference:**  
- [Checkpoint API](../api/checkpoint.md)  
- [Reducer Spec](../BACKPACK_PROTOCOL_v1.0.md#reducer-determinism)
