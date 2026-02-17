# Provara JSON Schemas

This directory contains machine-readable JSON Schemas for Provara Protocol v1.0.

## Files

- `provara_event_schema_v1.json`: envelope + payload validation for core event types:
  - `GENESIS`
  - `OBSERVATION`
  - `ASSERTION`
  - `ATTESTATION`
  - `RETRACTION`
  - `KEY_REVOCATION`
  - `KEY_PROMOTION`
  - `REDUCER_EPOCH`
  - Custom reverse-domain event types

## Notes

- Schema draft: 2020-12.
- Unknown fields are allowed by design to preserve forward compatibility.
- Runtime cryptographic checks (signature validity, causal chain, key revocation status) are out of scope for JSON Schema and must be enforced by verifier/sync logic.
