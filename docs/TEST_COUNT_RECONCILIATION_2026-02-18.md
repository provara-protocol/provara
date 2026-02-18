# Test Count Reconciliation (2026-02-18)

## Commands Run

```bash
python -m pytest -v --tb=short 2>&1
python -m pytest -v --co 2>&1
```

## Results

- Collected tests: `337`
- Executed tests: `337`
- Passed: `335`
- Skipped: `2`
- Failed: `0`
- XFail/XPas: `0` / `0`

Execution summary (Python 3.12, Windows):

```text
================ 335 passed, 2 skipped, 51 warnings in 41.97s =================
```

## Per-File Test Counts

| File | Count |
|---|---:|
| `tests/test_adversarial.py` | 20 |
| `tests/test_bootstrap.py` | 16 |
| `tests/test_byzantine_scenarios.py` | 8 |
| `tests/test_byzantine_sim.py` | 4 |
| `tests/test_canonicalization_properties.py` | 14 |
| `tests/test_checkpoint_v0.py` | 3 |
| `tests/test_cli.py` | 17 |
| `tests/test_conformance_kit.py` | 1 |
| `tests/test_crypto_coverage.py` | 27 |
| `tests/test_forgery.py` | 3 |
| `tests/test_forgery_attacks.py` | 12 |
| `tests/test_fuzz_canonical_json.py` | 23 |
| `tests/test_fuzz_events.py` | 13 |
| `tests/test_manifest_generator.py` | 15 |
| `tests/test_package.py` | 3 |
| `tests/test_perception_v0.py` | 3 |
| `tests/test_property_fuzzing.py` | 18 |
| `tests/test_reducer_v0.py` | 40 |
| `tests/test_rekey.py` | 24 |
| `tests/test_sync_v0.py` | 64 |
| `tests/test_timestamp.py` | 1 |
| `tests/test_vectors.py` | 8 |
| **Total** | **337** |

## Skipped / Conditional Tests

`tests/test_manifest_generator.py` has 2 platform-conditional skips on Windows:

- `Symlinks not supported on this platform` (2 tests)

No xfail tests were collected.

## Reconciliation: 337 vs 197 vs 18

- `337` is the current full `pytest` collection under `tests/` and is the correct whole-suite count.
- `197` came from running a **subset** during prior agent work (targeted suites, not full collection).
- `18` is the compliance verifier run (`tests/backpack_compliance_v1.py`), which is a dedicated conformance suite and not the full project test count.

## Failure Categorization

No failing tests in the current run, so no categories apply.

## TODO.md Note

`TODO.md` line 20 was updated locally to:

`337 tests (335 passed, 2 skipped, 0 failed on Python 3.12/Windows)`.

This file is local/tracker-oriented and may be gitignored depending on repo configuration.
