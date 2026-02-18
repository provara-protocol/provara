# SCITT Mapping: Provara Protocol

## Overview
SCITT (Supply Chain Integrity, Transparency, and Trust) is an IETF effort for tamper-evident signed statements plus independently verifiable receipts. It defines interoperable integrity semantics across issuers, transparency services, and verifiers.

Provara should align because SCITT is becoming the neutral trust vocabulary for software and AI attestations. Alignment improves ecosystem interoperability and gives Provara a standards-native story for enterprise and government credibility.

## Concept Mapping

| SCITT Concept | Provara Equivalent | Gap |
|--------------|-------------------|-----|
| Signed Statement | Signed Event | Format: COSE/CBOR vs JSON+Ed25519 |
| Transparency Service | Vault | Architecture: service-first vs file-first |
| Receipt | Verification Result / Checkpoint | Provara checkpoints are richer state artifacts |
| Issuer | Actor | Direct mapping |
| Artifact | Event Data (`payload`) | Direct mapping |
| Merkle Proof | Manifest + Merkle Root | Compatible structure |
| Registration Policy | Vault Policy (`sync_contract`, safety policy) | Provara adds safety-tier semantics |

## Format Differences
- SCITT common profile is COSE over CBOR; Provara uses canonical JSON plus Ed25519 signatures.
- SCITT deployments are typically server/transparency-log first; Provara is file/vault first and syncs later.
- SCITT statements are usually per-issuer objects; Provara supports multi-actor evidence chains in one vault.

## Interop Bridge

### Provara Event -> SCITT Signed Statement
- Map `event_id` to statement identifier (`subject` or statement metadata).
- Map `actor_key_id` and public key material to SCITT issuer identity fields.
- Convert canonical JSON bytes into COSE payload bytes and sign with COSE envelope.
- Preserve `prev_event_hash` and `ts_logical` as extension claims so causal-chain semantics survive translation.

### SCITT Receipt -> Provara Checkpoint
- Parse SCITT receipt transparency data (tree size, inclusion proof, service identity).
- Encode receipt metadata as a Provara checkpoint extension or as an attestation event.
- Bind receipt to `merkle_root` and `last_event_id` so replay verifiers can re-check inclusion.

### COSE Compatibility Layer Placement
A COSE adapter should live at the boundary layer (`export`/`import` tooling), not in the reducer or canonical event core. The core remains JSON-native; bridges handle COSE encoding/decoding as optional interop modules.

## Provara as a SCITT Profile
Provara can be positioned as a file-based SCITT profile:
- It meets transparency requirements via append-only, hash-chained evidence and replayable histories.
- It meets integrity requirements via deterministic canonicalization and signature verification.
- It uses a different transport model (local files and sync bundles instead of mandatory HTTP APIs) while preserving equivalent verifiability properties.

## Action Items for Full SCITT Compatibility
- [ ] COSE signing option (Phase 2)
- [ ] SCITT Receipt format export
- [ ] SCITT Transparency Service API adapter
- [ ] Formal SCITT profile I-D

## References
- `draft-ietf-scitt-architecture`
- `draft-steele-cose-merkle-tree-proofs`
- `draft-kamimura-scitt-vcp-01`
