# Conformance Kit v1

The Conformance Kit verifies whether a candidate Provara-compatible vault output is conformant to v1.0 behavior.

## Command

```bash
python tools/conformance/verify_impl.py --vault /path/to/vault
```

## What It Checks

1. **Schema sanity**  
   Core event envelope and per-type payload required fields.
2. **Chain + signature integrity**  
   Event ID derivation, per-actor chain linkage, and signature verification using registered public keys.
3. **Reducer hash parity**  
   Replay-derived `state_hash` parity against `state/current_state.json` when present.
4. **Normative vectors** (optional)  
   Executes `SNP_Core/test/test_vectors.py`.
5. **Compliance suite** (optional)  
   Executes `SNP_Core/test/backpack_compliance_v1.py` against the candidate vault.

## Options

```bash
python tools/conformance/verify_impl.py --vault /path/to/vault --skip-vectors --skip-compliance
python tools/conformance/verify_impl.py --vault /path/to/vault --json
```

- `--skip-vectors`: skip vector suite execution
- `--skip-compliance`: skip 17-test compliance suite execution
- `--json`: emit machine-readable summary

## Exit Codes

- `0`: all enabled checks passed
- `1`: one or more checks failed
- `2`: invalid invocation (e.g., vault path missing)

## Notes

- This kit is dependency-free (stdlib + project modules).
- It is designed for cross-language port validation workflows.
- Use together with:
  - `docs/BACKPACK_PROTOCOL_v1.0.md`
  - `docs/ERROR_CODES.md`
  - `test_vectors/vectors.json`
