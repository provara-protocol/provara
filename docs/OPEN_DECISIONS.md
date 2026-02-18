# Open Spec Decisions (Reconstructed)

Date: 2026-02-17
Scope reviewed: `PROTOCOL_PROFILE.txt`, `SNP_Core/bin/*`, `SNP_Core/test/test_reducer_v0.py`, `SNP_Core/test/test_rekey.py`, `SNP_Core/test/test_bootstrap.py`, `SNP_Core/test/test_sync_v0.py`

This document reconstructs design decisions that are materially implemented but not fully pinned by the frozen profile text.

## 1) Attestation Resolution for Existing `contested/` Keys

Description: What to do when an `ATTESTATION` arrives for a key currently in `contested/`, including a third value not seen in existing evidence.

Current implementation choice: `ATTESTATION` always writes canonical value, archives previous canonical if present, and unconditionally clears both `local/` and `contested/` for that key.

Alternative approaches:
- Preserve `contested/` history until explicit closure event.
- Reject attestations whose value is not one of contested evidence values.
- Require quorum/multi-attester threshold before contested cleanup.

Recommendation: Keep current behavior for v1.0 (deterministic, simple), and add an explicit optional provenance link to contested evidence set in v1.1.

## 2) RETRACTION Semantics for `archived/`

Description: Whether retracting canonical truth should delete it, tombstone it, or archive it.

Current implementation choice: If key is canonical, move canonical entry to `archived/` with `retracted=true` and `superseded_by=<retraction_event_id>`, then remove from canonical; always remove from local/contested.

Alternative approaches:
- Hard-delete canonical/local/contested without archived trace.
- Keep canonical entry with an in-place `retracted=true` marker.
- Separate `retracted/` namespace.

Recommendation: Keep current archival-tombstone behavior; it best matches append-only audit goals.

## 3) Reducer Trust Boundary for Revoked Keys

Description: Whether reducer must reject events signed by revoked keys.

Current implementation choice: Reducer does no signature/trust validation and applies events based on type/payload only; key validity is enforced in signing/sync layers (`resolve_public_key` rejects revoked keys for verification).

Alternative approaches:
- Reducer validates signatures and key status inline.
- Reducer receives only pre-verified events and hard-fails on unverified input marker.
- Split reducer modes: strict (verified-only) and permissive.

Recommendation: Preserve separation of concerns in v1.0, but specify a normative pipeline order: verify first, reduce second.

## 4) Merge Ordering When `timestamp_utc` Ties

Description: Deterministic global ordering rule for union merge when timestamps are identical.

Current implementation choice: Sort key is `(timestamp_utc, event_id)`; missing values sort as empty strings.

Alternative approaches:
- `(timestamp_utc, actor, ts_logical, event_id)`.
- Preserve source log order as secondary tiebreaker.
- Sort by content hash fallback when event_id absent.

Recommendation: Document current `(timestamp_utc, event_id)` rule as normative for v1.0 interoperability.

## 5) Event Identity/Dedup When `event_id` Is Missing

Description: Dedup behavior for malformed/legacy events lacking `event_id`.

Current implementation choice: Use `event_id` if present; otherwise deduplicate by canonical hash of full event object.

Alternative approaches:
- Reject all events missing `event_id`.
- Accept but never dedup missing-`event_id` records.
- Assign synthetic local IDs before merge.

Recommendation: Keep content-hash fallback for resilience, and add profile language that this is implementation-defined fallback (not canonical event identity).

## 6) Malformed NDJSON Handling in Sync/Import

Description: Whether malformed event lines fail the whole operation or are skipped.

Current implementation choice: `load_events()` silently skips malformed lines; `import_delta()` rejects malformed lines individually and continues, reporting errors.

Alternative approaches:
- Fail-fast on first malformed line.
- Quarantine malformed lines in sidecar file.
- Strict mode CLI flag with fail-fast behavior.

Recommendation: Keep permissive default for operational continuity; add strict mode in future CLI for forensic workflows.

## 7) Unknown Event Types and Metadata Accounting

Description: Unknown/custom type handling impact on reducer output and metadata counters.

Current implementation choice: Unknown types are ignored for core namespaces but still increment metadata event counters and update last event id; unknown type names are tracked in `_ignored_types`.

Alternative approaches:
- Unknown types do not increment event_count.
- Store unknown events in dedicated exported namespace.
- Hard-reject unknown types unless extension prefix present.

Recommendation: Keep current behavior and formalize that metadata counters represent processed log entries, not semantic state mutations.

## 8) State Hash Scope vs Metadata in Implementation

Description: Profile says hash state without metadata block; implementation hashes namespaces plus selected metadata fields (`last_event_id`, `event_count`, `current_epoch`, reducer config), excluding `metadata.state_hash`.

Current implementation choice: `state_hash = SHA-256(canonical(hashable_state_with_metadata_partial))`.

Alternative approaches:
- Strict profile interpretation: hash only four namespaces.
- Hash entire metadata (except self hash).
- Dual hashes: semantic hash (namespaces only) and operational hash (with metadata).

Recommendation: Define two hashes in next revision and keep current hash as legacy `state_hash_v0` for backward compatibility.

---

## Priority Actions

1. Normatively document pipeline ordering: signature/key verification precedes reducer application.
2. Freeze merge ordering and missing-`event_id` fallback language in the human-readable protocol spec.
3. Resolve state-hash scope mismatch explicitly before non-Python ports rely on ambiguous text.

---

## Rust Implementation Findings (2026-02-18)

During implementation of `provara-rs` (Lane 5B), the following spec ambiguities were discovered:

### 9) Minus Zero Handling in Canonical JSON

**Description:** The conformance suite includes a test for `-0.0` vs `0.0`. The Python implementation preserves `-0.0` as distinct from `0.0`, but IEEE 754 semantics consider them equal.

**Current Rust implementation choice:** The Rust implementation normalizes `-0.0` to `0.0` (via the `if s == "-0" { s = "0".to_string(); }` check).

**Alternative approaches:**
- Preserve `-0.0` as byte-distinct from `0.0` (matches Python behavior)
- Always normalize to `0.0` (matches JSON spec intent)
- Document as implementation-defined

**Recommendation:** For v1.0, preserve Python behavior (keep `-0.0` distinct). This requires updating the Rust implementation to not normalize minus zero. The conformance test `number_formatting_minus_zero` expects `-0.0` to be preserved.

**Status:** ⚠️ **ACTION REQUIRED** — Rust implementation needs update to match Python behavior.

### 10) Event ID Test Vector Uses Different Actor Format

**Description:** The test vector `event_id_derivation_01` uses `"actor": "bp1_actor_id"` which is not a valid key ID format (should be `bp1_` + 16 hex chars).

**Current Rust implementation choice:** The test accepts any string as actor, since actor validation is separate from event ID derivation.

**Alternative approaches:**
- Validate actor format before computing event ID
- Treat test vector as illustrative, not normative
- Update test vector to use valid key ID format

**Recommendation:** The test vector is illustrative. The Rust implementation correctly derives event ID regardless of actor format. Consider updating test vector to use a valid key ID format for clarity.

**Status:** ℹ️ **DOCUMENTED** — No code change needed, but test vector could be clearer.

### 11) Ed25519 Test Vector Uses Fixed Key Pair

**Description:** The test vector `ed25519_sign_verify_01` provides a public key and expected signature, but signatures are non-deterministic without a fixed seed. The expected signature cannot be verified without the corresponding private key.

**Current Rust implementation choice:** The test generates a random keypair and tests sign/verify round-trip, but does not validate against the expected signature in the test vector.

**Alternative approaches:**
- Include private key in test vector (for deterministic signing)
- Use a known-answer test with pre-computed signature
- Skip signature validation against expected value

**Recommendation:** Update test vector to include the private key (Base64 encoded) so implementations can reproduce the exact signature. Alternatively, provide a separate signature verification test with known message/signature/public_key triplet.

**Status:** ⚠️ **ACTION REQUIRED** — Test vector needs private key for full validation.

### 12) Reducer Determinism Test Vector is Simplified

**Description:** The test vector `reducer_determinism_01` expects a state hash computed from a simplified state structure (`{"canonical": {...}, "events_processed": N}`), but the Python reducer includes additional fields.

**Current Rust implementation choice:** The Rust implementation computes state hash from a minimal state structure, which may not match the Python reference implementation's full state hash.

**Alternative approaches:**
- Define full reducer state structure in test vector
- Provide expected intermediate state after each event
- Separate "state hash computation" from "reducer logic" tests

**Recommendation:** This test vector validates the concept of reducer determinism, not the exact Python reducer implementation. A full reducer test would require the complete state structure including all four namespaces (canonical, local, contested, archived).

**Status:** ℹ️ **DOCUMENTED** — Test vector is illustrative. Full reducer conformance requires separate test suite.

### 13) Merkle Root Test Vector Has Typo

**Description:** The test vector `merkle_root_01` has a hash value with incorrect casing: `"315f5bdb76d078c43b8ac00c33e22F06d20353842d059013e96196a84f33161"` contains uppercase `F` which is non-standard for hex encoding.

**Current Rust implementation choice:** The implementation lowercases all hex output, but accepts mixed-case input.

**Alternative approaches:**
- Normalize hex input to lowercase before comparison
- Fix test vector to use consistent lowercase
- Document hex encoding as case-insensitive

**Recommendation:** Fix test vector to use consistent lowercase hex encoding. The Provara spec requires "64 lowercase hexadecimal characters".

**Status:** ⚠️ **ACTION REQUIRED** — Test vector should be corrected to lowercase.

---

## Summary of Required Actions

| ID | Issue | Severity | Action |
|----|-------|----------|--------|
| 9 | Minus zero handling | Medium | Update Rust to preserve `-0.0` |
| 10 | Actor format in test vector | Low | Document as illustrative |
| 11 | Missing private key in signature test | High | Add private key to test vector |
| 12 | Simplified reducer test | Medium | Document limitations |
| 13 | Mixed-case hex in test vector | Low | Fix test vector to lowercase |

**Owner review required:** Items 9, 11, and 13 require decisions or test vector updates.
