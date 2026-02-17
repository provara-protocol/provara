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
