# Provara Key Compromise Recovery Protocol

**Version:** 1.0  
**Date:** 2026-02-18  
**Status:** Normative Specification  
**Protocol Version:** 1.0 (Profile A)

---

## 1. Discovery and Declaration

A key compromise is declared when a private key is known or suspected to be in the possession of an unauthorized actor.

**Indicators of Compromise:**
- Unauthorized events appearing in the log.
- Physical loss of a hardware security module (HSM) or YubiKey.
- Compromise of the storage environment where keys are held.
- Anomalous `ts_logical` jumps or `timestamp_utc` skews signed by the key.

---

## 2. Immediate Response

Upon discovery, the following actions MUST be taken immediately:

1.  **Isolate the Vault:** Stop all automated sync processes to prevent the spread of potentially forged events.
2.  **Identify Trust Boundary:** Determine the `trust_boundary_event_id`. This is the last known legitimate event signed by the compromised key.
3.  **Execute Revocation:** A surviving authority MUST append a `KEY_REVOCATION` event.

**Revocation Payload:**
```json
{
  "revoked_key_id": "bp1_compromised",
  "reason": "key_compromise",
  "trust_boundary_event_id": "evt_last_good_id",
  "revoked_at_utc": "2026-02-18T14:00:00Z"
}
```

---

## 3. Trust Boundary and Quarantining

All events signed by the compromised key with a `ts_logical` or `timestamp_utc` greater than the `trust_boundary_event_id` are considered **Suspect**.

- **Reducer Logic:** Compliant reducers SHOULD move suspect claims to the `contested/` namespace.
- **Verification:** `provara verify` will flag any events signed by a revoked key after its revocation event as **INVALID**.

---

## 4. Re-Attestation Process

To restore "Truth" to the vault, legitimate beliefs that were signed by the compromised key after the compromise (but before revocation) must be re-attested.

### Step 1: Identification
Filter the event log for events signed by the compromised key after the `trust_boundary_event_id`.

### Step 2: Verification
Manually or through secondary evidence (e.g., RFC 3161 timestamps), verify which suspect events were actually legitimate.

### Step 3: Re-Attestation Event
For each verified legitimate event, the new (promoted) key signs an `ATTESTATION` event that references the suspect event.

**Payload Structure:**
```json
{
  "type": "ATTESTATION",
  "actor": "recovery_authority",
  "payload": {
    "target_event_id": "evt_suspect_id",
    "status": "verified_legitimate",
    "evidence_hash": "sha256_of_original_payload",
    "note": "Re-attestation following key rotation"
  }
}
```

---

## 5. Forensic Export

For legal or audit purposes, a Provara vault can export a **Forensic Evidence Package**.

**Export Format:**
- The full `events.ndjson` up to the point of recovery.
- The `identity/keys.json` containing the revocation records.
- All RFC 3161 timestamp responses (`.tsr` files) associated with the vault state.

**Expert Review:**
A court expert can use the `prev_event_hash` chain to prove that the attacker could not delete evidence, only add to it, and that the `trust_boundary_event_id` is anchored by an external timestamp.

---

## 6. Single-Key Vaults: The Catastrophic Case

If a vault has only one key and it is compromised, there is **no surviving internal authority** to sign a revocation.

**Options:**
1.  **Identity Death:** The vault is permanently tainted. The owner must start a new vault (`init`) and manually cross-reference the old Merkle root in the new `GENESIS` payload.
2.  **External Anchor Recovery:** If the vault was configured with an `archive_peer` or `designated_human` in the `degradation_ladder`, that external entity can sign a "Restoration" event.

**Honest Assessment:** Without a second key or an external anchor, a single-key compromise effectively ends the cryptographic sovereignty of that vault.

---

## 7. Interaction with RFC 3161 Timestamps

RFC 3161 timestamps provide independent temporal proof.
- If a `TIMESTAMP_ANCHOR` event exists for a state hash *H* that includes the `trust_boundary_event_id`, it is cryptographically impossible for an attacker to have modified the chain prior to that timestamp.
- **Recovery Strategy:** Use the last pre-compromise timestamp as the definitive "Safe State" from which to begin re-attestation.

---

## 8. Spec Gaps & Open Decisions

1.  **Quarantine API:** The protocol lacks a normative `QUARANTINE` event type to explicitly mark events as suspect without revoking the key (e.g., during investigation).
2.  **Batch Re-attestation:** For logs with thousands of suspect events, a `BATCH_ATTESTATION` type should be defined to avoid log bloat.
