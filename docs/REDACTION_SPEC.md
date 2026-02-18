# Provara Redaction Specification (v1.0)

## 1. Overview
Provara is an append-only protocol where "Deletion is an event, not an erasure." However, compliance with GDPR Article 17 (Right to Erasure) and other legal requirements necessitates a mechanism to remove sensitive content from the log without breaking the cryptographic integrity of the chain.

This specification defines the `com.provara.redaction` event type and the "Tombstone" pattern for content removal.

## 2. The Redaction Event
The `com.provara.redaction` event is a standard Provara event that documents the removal of content from a previous event.

### 2.1 Payload Schema
- `target_event_id` (string, required): The `event_id` of the event being redacted.
- `reason` (string, required): One of:
    - `GDPR_ERASURE`
    - `LEGAL_ORDER`
    - `VOLUNTARY_WITHDRAWAL`
    - `PII_EXPOSURE`
    - `OTHER`
- `reason_detail` (string, optional): Free-text explanation.
- `redaction_method` (string, required): One of:
    - `TOMBSTONE`: Content replaced with a marker.
    - `CRYPTO_SHRED`: Encryption keys deleted (see `privacy.py`).
    - `CONTENT_REPLACE`: Content replaced with non-sensitive placeholder.
- `authority` (string, required): Actor ID or legal reference that authorized the redaction.

### 2.2 Example
```json
{
  "type": "com.provara.redaction",
  "actor": "admin_actor",
  "payload": {
    "target_event_id": "evt_abc123",
    "reason": "GDPR_ERASURE",
    "redaction_method": "TOMBSTONE",
    "authority": "Legal Dept / Request #882"
  },
  "event_id": "evt_redact_999",
  "sig": "..."
}
```

## 3. The Tombstone Pattern
When an event is redacted using the `TOMBSTONE` method, the original record in `events.ndjson` is modified in-place.

### 3.1 Integrity Rules
1. **Preserve Identity**: The `event_id` MUST NOT change. This ensures the hash chain remains unbroken.
2. **Preserve Provenance**: The `type`, `actor`, `actor_key_id`, `ts_logical`, `prev_event_hash`, and `timestamp_utc` MUST be preserved.
3. **Preserve Evidence**: The original `sig` MUST be preserved. It proves that a validly signed event existed at that position in the chain.
4. **Replace Content**: The `payload` is replaced with a Tombstone Object.

### 3.2 Tombstone Object Schema
```json
{
  "redacted": true,
  "redaction_event_id": "evt_redact_999",
  "original_payload_hash": "sha256_of_original_payload",
  "redaction_reason": "GDPR_ERASURE"
}
```

## 4. Verification Behavior
Compliant verifiers (`provara verify`) MUST handle Tombstones as follows:

1. **Chain Validation**: `prev_event_hash` linkage is verified normally.
2. **Event ID Validation**: For redacted events, the verifier SHOULD NOT attempt to recompute the `event_id` from the current content, as it will naturally mismatch. Instead, it MUST verify that a corresponding `com.provara.redaction` event exists in the log.
3. **Signature Validation**: Signature verification will fail for the new content. Verifiers MUST accept the original signature as historical evidence if the event is marked `redacted: true`.

## 5. Security Considerations
- Redaction proves *intent* and *authority*. It does not hide the fact that an event existed.
- Once a vault is synced to other devices, redaction requires all peers to adopt the modified `events.ndjson`. Provara sync logic MUST prioritize redacted states for the same `event_id`.
