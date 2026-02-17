# PSMC

**Module:** `tools/psmc/psmc.py`

Personal Sovereign Memory Container. High-level application layer for vault operations.

## Overview

PSMC wraps Provara core modules in a user-friendly interface for:

- Creating and managing personal vaults
- Recording life events, decisions, and observations
- Querying beliefs with confidence scores
- Syncing across devices
- Generating digests and reports

## Quick Start

```python
from provara.psmc import PSMC
from pathlib import Path

# Open or create vault
container = PSMC(Path("My_Memory"))

# Record observation
container.record_observation(
    subject="health/sleep",
    predicate="hours",
    value=8,
    confidence=0.95
)

# Query beliefs
sleep_data = container.query("health/sleep", "hours")
# Returns: belief with 0.95 confidence

# Generate weekly digest
digest = container.generate_digest(days=7)
print(digest)
```

## Commands

- `record_observation` — Add an observation
- `record_decision` — Log a decision
- `query` — Query beliefs
- `list_conflicts` — Show conflicting observations
- `sync` — Merge with another vault
- `export` — Export as markdown or JSON

## References

- [Provara: PSMC Tutorial](https://provara.dev/docs/psmc/)
