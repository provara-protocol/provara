# checkpoint_v0

**Module:** `src/provara/checkpoint_v0.py`

Signed state snapshots for fast replay. Enables O(1) vault state access without full event log scan.

## Quick Start

```python
from provara.checkpoint_v0 import create_checkpoint, verify_checkpoint
from pathlib import Path

vault = Path("My_Backpack")

# Create checkpoint
checkpoint_path = vault / "state" / "checkpoint_2024-02-17.json"
create_checkpoint(vault, checkpoint_path, private_key_b64)

# Later: verify checkpoint
is_valid = verify_checkpoint(checkpoint_path, public_key_b64)
```

## References

- [Provara: Checkpoint Specification](https://provara.dev/spec/)
