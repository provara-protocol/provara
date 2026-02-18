# Provara ↔ SCITT Compatibility Mapping

**Status:** Architecture Review · **Date:** 2026-02-18 · **Lane:** 5C Standards Alignment

---

## Executive Summary

This document maps Provara Protocol v1.0 components to IETF SCITT (Supply Chain Integrity, Transparency and Trust) concepts. It identifies alignment, gaps, and the path to SCITT compatibility.

**Conclusion:** Provara can operate as a SCITT-compatible transparency service with minimal extensions. The core event model is already SCITT-aligned; the main gap is COSE envelope standardization and receipt format.

---

## SCITT Reference

**SCITT** (IETF draft, in development) defines a framework for transparent, auditable supply chain assertions. Key concepts:

- **Signed Statement** — A signed claim from a subject (e.g., artifact attestation, policy assertion)
- **Transparency Service** — Auditable ledger that accepts, verifies, and publishes statements
- **Receipt** — Proof of inclusion in the ledger (typically Merkle path + timestamp)
- **Verifier** — Third party that can independently verify receipt integrity

---

## Mapping

### 1. Provara Events ↔ SCITT Signed Statements

| SCITT | Provara | Mapping |
|-------|---------|---------|
| **Statement** | Event | Signed claim from an actor |
| **Subject** | Actor | The entity making the claim (e.g., alice@corp.com) |
| **Claim** | event_type + content | The assertion (OBSERVATION, ATTESTATION, etc.) |
| **Timestamp** | timestamp | When the statement was signed |
| **Signature** | sig (Ed25519) | Cryptographic proof of authorship |

**Example: Build Pipeline Attestation**

```json
// Provara OBSERVATION
{
  "event_id": "evt_abc123...",
  "actor": "ci-pipeline@corp.com",
  "event_type": "OBSERVATION",
  "timestamp": "2026-02-18T10:30:00Z",
  "content": {
    "artifact": "app-v1.0.0.jar",
    "sha256": "d2f1c2a...",
    "build_status": "PASSED",
    "tests": 420,
    "tests_passed": 420
  },
  "sig": "base64_encoded_ed25519_signature"
}

// Same as SCITT Signed Statement (in COSE envelope)
COSE_Sign1(
  protected: {alg: "EdDSA"},
  unprotected: {
    kid: "ci-pipeline@corp.com",
    iss: "https://corp.com",
    aud: "transparency-service"
  },
  payload: {
    "artifact": "app-v1.0.0.jar",
    "sha256": "d2f1c2a...",
    ...
  },
  signature: "..."
)
```

**Provara Advantage:** Uses RFC 8785 canonical JSON directly. COSE envelope is optional layer on top.

---

### 2. Provara Vault ↔ SCITT Transparency Service

| SCITT Aspect | Provara Vault | Notes |
|--------------|---------------|-------|
| **Statement Log** | vault.events (NDJSON) | Immutable log of all signed claims |
| **Merkle Tree** | merkle_root + manifest | Cryptographic proof of log completeness |
| **Temporal Proof** | timestamp field | Per-statement timestamps (with optional RFC 3161 anchor for legal admissibility) |
| **Indexing** | reducer state (4 namespaces) | canonical/local/contested/archived — epistemic status tracking |
| **Persistence** | append-only storage | Once written, never modified or deleted |
| **Verifier Access** | manifest + merkle_root | Public verify without private keys |

**Architectural Alignment:**

```
SCITT Transparency Service Model:
┌──────────────────┐
│ Signed Statements│ ← Submit (client sends signed claim)
│   (in log)       │
├──────────────────┤
│  Merkle Tree     │ ← Proof (verifier requests inclusion proof)
├──────────────────┤
│  Receipts        │ ← Receipt (with temporal anchor)
└──────────────────┘

Provara Vault Implementation:
┌──────────────────┐
│   Events (NDJSON)│ ← Submit (actor appends event)
│  Per-actor chain │
├──────────────────┤
│  manifest.json   │ ← Proof (contains merkle_root + hashes)
│  merkle_root.txt │
├──────────────────┤
│  Checkpoints     │ ← Receipt (optional: signed state snapshot)
│ (Optional)       │
└──────────────────┘
```

---

### 3. Provara Checkpoints ↔ SCITT Receipts

| SCITT Receipt | Provara Checkpoint | Mapping |
|---------------|------------------|---------|
| **Merkle Path** | merkle_proof in checkpoint | Proves inclusion at specific tree position |
| **Tree Head** | checkpoint.merkle_root | The root hash of the tree at that moment |
| **Timestamp** | checkpoint.timestamp | When the checkpoint was created |
| **Optional: TSA Anchor** | TIMESTAMP_ANCHOR event | RFC 3161 trusted timestamp (optional) |
| **Verifier** | checkpoint.sig (signed by vault authority) | Proves checkpoint authenticity |

**Example Provara Checkpoint (= SCITT Receipt)**

```json
{
  "checkpoint_id": "ckpt_xyz789...",
  "event_count": 42,
  "merkle_root": "abc123def456...",
  "timestamp": "2026-02-18T12:00:00Z",
  "prev_checkpoint_id": "ckpt_xyz788...",
  "sig": "ed25519_signature_by_vault_authority",
  
  // Optional: Legal admissibility
  "timestamp_anchor": {
    "tsa": "http://timestamp.authority.com",
    "token": "rfc3161_timestamp_token",
    "verified_at": "2026-02-18T12:00:05Z"
  }
}
```

---

### 4. Namespace Mapping

Provara's 4-namespace model maps to SCITT verification levels:

| Provara Namespace | SCITT Concept | Meaning |
|-------------------|---------------|---------|
| **canonical** | Attested (verified) | Statements that passed verification policies |
| **local** | Unverified | Locally created assertions (not yet attested) |
| **contested** | Under Review | Conflicting statements; disputed assertions |
| **archived** | Historical | Resolved or superseded statements (kept for audit trail) |

**Policy Example:**

```
OBSERVATION event from untrusted actor
  → Starts in "local" namespace
  → ATTESTATION from trusted verifier appended
  → Reducer moves it to "canonical" (trusted)
  
If two actors disagree (fork):
  → Both observations in "contested"
  → Tie-breaker ATTESTATION resolves (move one to canonical, one to archived)
```

---

### 5. Key Management Alignment

| SCITT | Provara | Notes |
|-------|---------|-------|
| **KID (Key ID)** | key_id = "bp1_" + SHA256(pubkey)[:16] | Content-addressed, deterministic |
| **Key Authority** | Actor + active keys | Per-actor keypair management |
| **Key Rotation** | KEY_REVOCATION + KEY_PROMOTION | Two-event atomic rotation |
| **Non-Repudiation** | Ed25519 + prev_hash chain | Signatures + causal chain = immutable authorship |

---

## Gap Analysis: Provara → Full SCITT Compliance

### Already Aligned ✓

1. ✅ **Signed claims** — Ed25519 signatures (SCITT allows algorithms beyond COSE)
2. ✅ **Immutable log** — Append-only events chained by prev_hash
3. ✅ **Merkle proofs** — Manifest includes file hashes and computed merkle_root
4. ✅ **Temporal ordering** — Timestamps on every event
5. ✅ **Deterministic verification** — RFC 8785 canonicalization guarantees reproducibility
6. ✅ **Non-repudiation** — Ed25519 signatures + chain of custody

### Minor Gaps (Bridgeable)

| Gap | Provara Status | SCITT Requirement | Solution |
|-----|----------------|-------------------|----------|
| **COSE Envelope** | JSON + Ed25519 | Optional; COSE is one choice | Wrap JSON in COSE_Sign1 if integrating with COSE-native verifiers |
| **Receipt Format** | Checkpoint | Standardized merkle path | Define `scitt_receipt` event type (reverse-domain: `org.ietf.scitt.receipt`) |
| **TSA Integration** | Optional (rfc3161-client) | Recommended | Implement RFC 3161 anchor as TIMESTAMP_ANCHOR event |
| **Verifier API** | Implicit (manifest) | Standardized endpoint | Define REST API for `/verify` (non-core, application layer) |

### Non-Blocking Differences (By Design)

| Provara | SCITT | Why Different |
|---------|-------|---------------|
| File-first (vault.provara as file) | Service-first (centralized ledger) | Provara prioritizes portability; SCITT assumes service architecture |
| Per-actor causal chains | Global linearized log | Provara: distributed model. SCITT: centralized transparency |
| 4 namespaces (epistemic tiers) | Flat statement list | Provara adds policy ratchet; SCITT is agnostic to policy |
| Checkpoint = signed state snapshot | Receipt = merkle path only | Provara: idempotent snapshots. SCITT: minimal receipts |

---

## Implementation Path: "SCITT-Compatible Provara"

### Phase 1: Minimal Compatibility (2 days)

Add two new event types:

```typescript
// Core Provara (existing)
type CoreEventType = 'OBSERVATION' | 'ATTESTATION' | 'RETRACTION';

// SCITT Compat Extension (new)
type SCITTEventType = 'com.ietf.scitt.signed_statement' | 'com.ietf.scitt.receipt';
```

**Step 1:** Define `com.ietf.scitt.signed_statement` event type
- Wrapper around COSE_Sign1 or SCITT standard envelope
- Parsed and indexed like any other event
- Unknown event types preserved per PROTOCOL_PROFILE.txt extension rules

**Step 2:** Define `com.ietf.scitt.receipt` event type
- Stores merkle path + tree head + TSA token
- Consumable by SCITT verifiers
- Completes the receipt chain

### Phase 2: Verifier Integration (3 days)

Build a `SCITTVerifier` that:

1. Reads Provara vault.events
2. Filters for core event types + SCITT extensions
3. Exports as SCITT-compatible JSON
4. Generates merkle paths for receipt verification

```python
# Python CLI
provara export --format scitt-compat vault.provara > scitt_export.json

# Output: JSON array of statements + receipts, ready for any SCITT verifier
```

### Phase 3: Upstream Alignment (1–2 weeks)

1. **Submit to IETF SCITT WG** — "Provara as SCITT Reference Implementation"
2. **Request KID namespace** — Officially register `bp1_` prefix in IANA Signature Algorithm Registry
3. **Contribute test vectors** — Cross-check with other SCITT implementations (Sigstore, etc.)

---

## Competitive Positioning

### Why Provara Wins on SCITT

| Property | Sigstore | Git | Provara |
|----------|----------|-----|---------|
| **SCITT Draft Aligned** | ✓ (native) | ✗ (not designed for) | ✓ (bridgeable) |
| **Portability** | HTTP API only | Git repos | 📁 File-first + HTTP optional |
| **50-year Readiness** | ❓ (cert expiry risk) | ✓ (git history) | ✓✓ (designed for it) |
| **Distributed** | ✗ (centralized service) | ✓ (peer-to-peer) | ✓ (hybrid) |
| **Policy Layers** | ✗ | ✗ | ✓ (4-tier safety model) |

**Market Angle:** "Provara is Git for supply chain evidence. SCITT-compatible, but not dependent on any service. Audit trail lives in your repo."

---

## Reference Documents

### SCITT Specification
- [IETF SCITT Architecture](https://datatracker.ietf.org/doc/draft-ietf-scitt-architecture/)
- [IETF SCITT Transparency Service](https://datatracker.ietf.org/doc/draft-ietf-scitt-transparency-service/)
- [CoRIM + CoMID (Supply Chain Evidence)](https://datatracker.ietf.org/doc/draft-ietf-rats-corim/)

### Provara Spec
- [`PROTOCOL_PROFILE.txt`](../PROTOCOL_PROFILE.txt)
- [`BACKPACK_PROTOCOL_v1.0.md`](BACKPACK_PROTOCOL_v1.0.md)

### Related Standards
- [RFC 8785 — JSON Canonicalization Scheme](https://tools.ietf.org/html/rfc8785)
- [RFC 8032 — Edwards-Curve Digital Signature Algorithm (EdDSA)](https://tools.ietf.org/html/rfc8032)
- [RFC 3161 — Time-Stamp Protocol (TSP)](https://tools.ietf.org/html/rfc3161)
- [RFC 9052 — CBOR Object Signing and Encryption (COSE)](https://tools.ietf.org/html/rfc9052)

---

## Next Steps

1. ✅ **This mapping document** — DELIVERED
2. → **Phase 1 Implementation** — Add SCITT event types (2 days)
3. → **Phase 2 Verifier** — Build export tool (3 days)
4. → **Phase 3 Submission** — IETF SCITT WG alignment (optional, high-leverage)

---

**"Truth is not merged. Evidence is merged. Truth is recomputed."**
