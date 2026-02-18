# Provara Crypto-Shredding Specification (v1.0)

**Date:** 2026-02-18  
**Status:** Implementation specification  
**Related:** [REDACTION_SPEC.md](REDACTION_SPEC.md), [privacy.py](../src/provara/privacy.py)

---

## 1. Problem Statement

### 1.1 The Conflict

Provara is an append-only cryptographic event log. Events are:
- Immutable (by design)
- Cryptographically signed (Ed25519)
- Chained via hash links (tamper-evident)

GDPR Article 17 (Right to Erasure) requires:
- Deletion of personal data upon request
- Complete erasure within reasonable timeframe
- Notification to downstream processors

**Conflict:** Append-only logs cannot delete data. Tombstone redaction (the current approach) leaves metadata visible and payloads recoverable.

### 1.2 The Solution: Crypto-Shredding

Crypto-shredding encrypts event payloads at write time with per-event or per-actor keys. To "erase" data:
1. Destroy the encryption key
2. Ciphertext becomes permanently unrecoverable
3. Hash chain remains intact (hashes computed over ciphertext)

**Result:** GDPR compliance without breaking cryptographic integrity.

---

## 2. Design Overview

### 2.1 Encryption Envelope

Encrypted events use this structure:

```json
{
  "event_id": "evt_abc123...",
  "type": "OBSERVATION",
  "actor": "actor_alice",
  "timestamp_utc": "2026-02-18T12:00:00Z",
  "prev_event_hash": "evt_prev...",
  "data_encrypted": true,
  "payload": {
    "_privacy": "aes-gcm-v1",
    "kid": "dek_evt_abc123",
    "nonce": "<base64 12-byte nonce>",
    "ciphertext": "<base64 AES-GCM ciphertext>"
  },
  "signature": "<Ed25519 signature over entire event>",
  "public_key": "<base64 Ed25519 public key>",
  "key_id": "bp1_..."
}
```

**Key points:**
- `data_encrypted: true` — flag indicating encrypted payload
- `payload._privacy` — privacy wrapper schema version
- `payload.kid` — Data Encryption Key identifier
- `payload.nonce` — AES-GCM nonce (12 bytes, Base64-encoded)
- `payload.ciphertext` — Encrypted data (Base64-encoded)
- Signature covers entire event including ciphertext

### 2.2 Key Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│  Key Encryption Key (KEK)                                   │
│  - Stored separately (operator-managed, not in vault)       │
│  - Wraps DEKs for backup/rotation                           │
│  - Destroying KEK = erases all actor's events               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ wraps
┌─────────────────────────────────────────────────────────────┐
│  Data Encryption Keys (DEKs)                                │
│  - Per-event (mode A) or per-actor (mode B)                 │
│  - AES-256-GCM keys (32 bytes)                              │
│  - Stored in vault/identity/privacy_keys.db                 │
│  - Destroying DEK = erases single event                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ encrypts
┌─────────────────────────────────────────────────────────────┐
│  Event Payloads                                             │
│  - JSON objects                                             │
│  - Encrypted before signing                                 │
│  - Hash chain computed over ciphertext                      │
└─────────────────────────────────────────────────────────────┘
```

### 2.3 Encryption Modes

| Mode | Key Scope | Use Case | Trade-offs |
|------|-----------|----------|------------|
| **Per-event** | One DEK per event | Fine-grained erasure | More keys to manage |
| **Per-actor** | One DEK per actor | Simple key management | Erasing one = erasing all |

---

## 3. Key Storage

### 3.1 DEK Storage (Mutable Sidecar)

DEKs are stored in a SQLite database separate from the append-only event log:

**Path:** `vault_path/identity/privacy_keys.db`

**Schema:**
```sql
CREATE TABLE keys (
    key_id TEXT PRIMARY KEY,
    key_bytes BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actor_id TEXT,  -- for per-actor mode
    event_id TEXT   -- for per-event mode
);
```

**Why SQLite?**
- Mutable (keys can be deleted)
- Transactional (atomic shred operations)
- No external dependencies (stdlib sqlite3)

### 3.2 KEK Storage (External)

KEKs are stored outside the vault:
- Hardware Security Module (HSM)
- Cloud KMS (AWS KMS, Azure Key Vault, GCP KMS)
- YubiKey or other hardware tokens

**KEK purposes:**
- Wrap DEKs for backup
- Rotate DEKs without re-encryption
- Bulk erasure (destroy KEK = erase all)

---

## 4. Shredding Ceremony

### 4.1 Single Event Shredding

To shred a single event:

1. **Verify authority:** Check requester has permission (via signed request)
2. **Record shred event:** Append `com.provara.crypto_shred` event to log
3. **Delete DEK:** Remove key from `privacy_keys.db`
4. **Update manifest:** Regenerate manifest and Merkle root

**Shred event payload:**
```json
{
  "type": "com.provara.crypto_shred",
  "actor": "admin_actor",
  "payload": {
    "target_event_id": "evt_abc123",
    "reason": "GDPR_ERASURE",
    "reason_detail": "Data subject request #882",
    "authority": "Legal Dept",
    "shred_scope": "single_event"
  }
}
```

### 4.2 Actor-Wide Shredding

To shred all events by an actor:

1. **Verify authority:** Check requester has permission
2. **Record shred event:** Append `com.provara.crypto_shred` event
3. **Delete all actor DEKs:** Query `privacy_keys.db` by `actor_id`
4. **Update manifest:** Regenerate manifest and Merkle root

**Shred event payload:**
```json
{
  "type": "com.provara.crypto_shred",
  "actor": "admin_actor",
  "payload": {
    "target_actor_id": "actor_alice",
    "reason": "GDPR_ERASURE",
    "reason_detail": "Account closure request",
    "authority": "Legal Dept",
    "shred_scope": "actor_wide",
    "events_affected": 47
  }
}
```

### 4.3 Audit Trail

The shred event is:
- **Permanent:** Cannot be deleted (it's the audit trail)
- **Signed:** Proves authorized shredding
- **Verifiable:** Anyone can verify shredding was authorized

**What remains after shredding:**
- Event metadata (event_id, type, actor, timestamp)
- Ciphertext (unrecoverable without key)
- Shred event (proves authorized erasure)

**What is destroyed:**
- Plaintext payload (cryptographically unrecoverable)
- DEK (deleted from key store)

---

## 5. Verification Behavior

### 5.1 Chain Verification

Hash chain verification works normally:
- `prev_event_hash` links are preserved
- Event IDs are computed over ciphertext (unchanged)
- Signatures cover ciphertext (still valid)

### 5.2 Content Verification

For shredded events:
- Decryption fails (key not found)
- Verifier reports: "Event shredded, content unrecoverable"
- This is **expected behavior**, not an error

### 5.3 Verify Output

```bash
$ provara verify my-vault

Vault Verification Report
=========================

Chain Integrity: PASS
Signatures: PASS
Merkle Root: PASS

Events: 150 total
  - 145 normal events
  - 5 shredded events (content unrecoverable)

Shredded Events:
  - evt_abc123 (shredded 2026-02-18, reason: GDPR_ERASURE)
  - evt_def456 (shredded 2026-02-18, reason: GDPR_ERASURE)

Status: PASS (with shredded events)
```

---

## 6. Comparison with VCP (draft-kamimura-scitt-vcp-01)

### 6.1 Similarities

| Feature | VCP | Provara |
|---------|-----|---------|
| Encryption algorithm | AES-256-GCM | AES-256-GCM |
| Key hierarchy | DEK + KEK | DEK + KEK |
| Hash chain | Computed over ciphertext | Computed over ciphertext |
| Shred operation | Delete DEK | Delete DEK |
| Audit trail | Shred event logged | Shred event logged |

### 6.2 Differences

| Feature | VCP | Provara |
|---------|-----|---------|
| Encryption scope | Per-field | Per-payload |
| Key scope | Per-subject | Per-event or per-actor |
| Key storage | External KMS | SQLite sidecar (DEK) + external (KEK) |
| Primary use case | Supply chain transparency | AI agent memory / audit logs |
| Redaction event | VCP-ERASURE | com.provara.crypto_shred |

### 6.3 Design Rationale

**Per-payload encryption (Provara) vs per-field (VCP):**
- Simpler implementation
- All or nothing erasure (no partial redaction)
- Smaller event size (one nonce, one ciphertext blob)

**SQLite sidecar (Provara) vs external KMS (VCP):**
- Self-contained vault (no external dependencies)
- Works offline (critical for sovereign deployments)
- KEK can still be external for high-security deployments

---

## 7. Security Considerations

### 7.1 Key Management

**DEKs:**
- Generated with CSPRNG (`os.urandom(32)`)
- Used once (per-event mode) or per actor (per-actor mode)
- Stored encrypted at rest (database encryption recommended)

**KEKs:**
- Never stored in vault
- Use HSM or cloud KMS for production
- Rotate annually or on personnel changes

### 7.2 Nonce Handling

AES-GCM requires unique nonces:
- Generated with CSPRNG (`os.urandom(12)`)
- Never reused with same key
- Stored alongside ciphertext (not secret)

### 7.3 Backup and Recovery

**Before shredding:**
- Backup `privacy_keys.db` separately from vault
- Encrypt backups with KEK
- Test restore procedures

**After shredding:**
- Data is permanently unrecoverable (by design)
- Ensure shred request is authorized and documented
- Notify downstream processors (GDPR requirement)

### 7.4 Side-Channel Considerations

**Timing attacks:**
- Decryption failure (key missing) should take same time as success
- Don't leak whether key existed before deletion

**Metadata leakage:**
- Event metadata (type, actor, timestamp) remains visible
- Consider encrypting metadata for high-privacy deployments

---

## 8. Implementation Guide

### 8.1 Creating Encrypted Vault

```bash
# Per-event encryption (fine-grained erasure)
provara init my-vault --encrypted --mode per-event

# Per-actor encryption (simpler key management)
provara init my-vault --encrypted --mode per-actor
```

### 8.2 Appending Encrypted Events

```bash
# Automatic encryption if vault is encrypted
provara append my-vault \
  --type OBSERVATION \
  --data '{"ssn": "123-45-6789", "name": "Alice"}' \
  --keyfile my-vault/identity/private_keys.json
```

### 8.3 Shredding Events

```bash
# Shred single event
provara shred my-vault \
  --event evt_abc123 \
  --reason GDPR_ERASURE \
  --keyfile my-vault/identity/private_keys.json

# Shred all events by actor
provara shred my-vault \
  --actor actor_alice \
  --reason GDPR_ERASURE \
  --keyfile my-vault/identity/private_keys.json
```

### 8.4 Verifying Encrypted Vault

```bash
# Normal verification (works with encrypted events)
provara verify my-vault

# Shows shredded events separately
# Hash chain still validates
```

---

## 9. GDPR Compliance Mapping

| GDPR Requirement | Provara Mechanism |
|------------------|-------------------|
| **Article 17 (Erasure)** | Crypto-shredding destroys DEK |
| **Article 18 (Restriction)** | Withhold DEK access (temporary restriction) |
| **Article 30 (Processing Records)** | Shred events document erasure |
| **Article 32 (Security)** | AES-256-GCM encryption at rest |
| **Article 33 (Breach Notification)** | Shred compromised keys, notify subjects |

---

## 10. References

- [REDACTION_SPEC.md](REDACTION_SPEC.md) — Tombstone redaction (alternative approach)
- [privacy.py](../src/provara/privacy.py) — Reference implementation
- [draft-kamimura-scitt-vcp-01](https://datatracker.ietf.org/doc/html/draft-kamimura-scitt-vcp-01) — VCP crypto-shredding design
- GDPR Article 17 — Right to erasure ('right to be forgotten')

---

*This specification is part of Provara v1.0. For changes or extensions, open a GitHub issue.*
