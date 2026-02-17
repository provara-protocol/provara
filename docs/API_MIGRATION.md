# API Migration Guide: `SNP_Core/bin` -> `provara` Package

This project has migrated to a standard Python package structure under `src/provara`.
Legacy `SNP_Core/bin` scripts have been removed.

## Imports

Update all imports to use the `provara` package:

| Old | New |
|-----|-----|
| `from reducer_v0 import SovereignReducerV0` | `from provara import SovereignReducer` |
| `from bootstrap_v0 import bootstrap_backpack` | `from provara import bootstrap_backpack` |
| `from sync_v0 import sync_backpacks` | `from provara import sync_backpacks` |
| `from backpack_signing import sign_event` | `from provara import sign_event` |
| `from canonical_json import canonical_dumps` | `from provara import canonical_dumps` |

## CLI

The `provara` command is now installed via `pip`.

```bash
# Old
python SNP_Core/bin/provara.py init ...

# New
provara init ...
# or
python -m provara.cli init ...
```
