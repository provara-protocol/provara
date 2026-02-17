# Test Matrix (Authoritative)

This file is the canonical verification contract during the `src/` migration.

## Core Commands

1. Unit (core protocol behavior)

```bash
cd tests && PYTHONPATH=../src:.. python -m unittest test_reducer_v0 test_rekey test_bootstrap test_sync_v0 -q
```

2. Compliance (reference backpack fixture)

```bash
python tests/backpack_compliance_v1.py tests/fixtures/reference_backpack -q
```

3. Normative vectors

```bash
cd tests && PYTHONPATH=../src:.. python test_vectors.py
```

4. Public package/API smoke

```bash
python -m pytest -q tests/test_package.py SNP_Core/test/test_public_api.py
```

## Makefile Targets

- `make test-unit`
- `make test-vectors`
- `make test-comply`
- `make test`

These targets are expected to mirror the commands above.

## Notes

- `PYTHONPATH=../src:..` is currently required because some tests still import legacy top-level shim modules (`reducer_v0`, `sync_v0`, `backpack_signing`) while package imports use `provara.*`.
- During migration, changes to test paths or fixture locations must also update:
  - `Makefile`
  - this file
  - `tools/check_test_layout.py`
