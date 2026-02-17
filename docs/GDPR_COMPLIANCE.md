# Provara Privacy & GDPR Compliance Architecture

> **Status:** Draft Technical Guidance
> **Date:** 2026-02-17
> **Context:** Reconciling append-only integrity with the "Right to Erasure" (GDPR Art. 17).

## The Paradox

Provara is designed to be **immutable**.
GDPR requires data to be **erasable**.

If PII (Personally Identifiable Information) is written directly into an immutable event log, the entire vault becomes toxic waste upon a deletion request. You cannot delete the event without breaking the hash chain.

## The Solution: Cryptographic Erasure ("Crypto-Shredding")

We do not delete the *record* that an event happened. We make the *content* identifying.

### Mechanism

1. **Per-Field Encryption:** Sensitive fields are not stored as plaintext.
2. **Ephemeral Keys:** Each sensitive value (or group of values) is encrypted with a unique, random 256-bit key (`data_key`).
3. **Key Storage:** The `data_key` is stored in a separate, mutable "Keyczar" or database, mapped to the `event_id`.
4. **The Event:** The vault stores `{"ciphertext": "...", "key_ref": "uuid"}`.
5. **Erasure:** To "delete" the data, we destroy the `data_key`.
   - The ciphertext remains in the immutable log.
   - The hash chain remains unbroken.
   - The data is mathematically unrecoverable (assuming AES-256-GCM is secure).

### Implementation Pattern

```python
# Recording
data_key = generate_key()
ciphertext = encrypt(pii, data_key)
key_id = store_key_mutably(data_key) # <--- The "Erase Button"
event = append_event(payload={"data": ciphertext, "kid": key_id})

# Reading
event = read_event(event_id)
data_key = fetch_key(event.payload.kid)
if not data_key:
    return "DATA_ERASED"
return decrypt(event.payload.data, data_key)

# Erasing
delete_key(key_id)
```

## Alternative: Off-Chain CAS (Content Addressed Storage)

For large blobs (images, documents), store only the `SHA-256` hash in the Provara event. Store the actual file in a local `artifacts/` directory or S3.

**Erasure:** Delete the file from `artifacts/`. The event remains as proof that "File X existed at Time T," but the content is gone.

## Recommendation

- **Use Crypto-Shredding** for structured event data (names, emails) that must live "inside" the event flow.
- **Use Off-Chain CAS** for binaries and large unstructured data.
- **NEVER** put plaintext PII in the `subject` or `predicate` fields (which are indexed).

---
*Disclaimer: This is engineering documentation, not legal advice. Consult counsel regarding specific GDPR/CCPA obligations.*
