# Show HN FAQ — Pre-Answered Questions

**Date:** 2026-02-18  
**Purpose:** Anticipate and answer likely HN questions before they're asked

---

## 1. "How is this different from a database with audit logging?"

Databases with audit logging (e.g., PostgreSQL with pg_audit) rely on trusting the database operator. The operator can modify rows, truncate logs, or alter timestamps without detection.

Provara provides cryptographic tamper evidence: every event is signed with Ed25519, linked via SHA-256 hash chains, and sealed with a Merkle tree. Any modification—even by the operator—breaks the chain and is immediately detectable. You can verify integrity without trusting anyone.

Tradeoff: You lose ACID transactions and complex queries. Provara is append-only with simple event filtering.

---

## 2. "Why not just use a blockchain?"

Blockchains solve consensus among untrusted parties. If you control your own vault (or trust the vault operator), you don't need consensus—you need integrity.

Provara provides:
- **Faster:** 171K events/second vs Bitcoin's 7 tx/s
- **Cheaper:** No mining, no gas fees
- **Simpler:** No consensus protocol, no tokens
- **Private:** No public ledger (unless you want one)

The hash chain provides tamper evidence without the overhead of decentralized consensus. It's closer to git than Bitcoin.

---

## 3. "Why Ed25519 and not <X>?"

Ed25519 (RFC 8032) was chosen for:
- **Deterministic signatures:** No RNG required (no nonce reuse vulnerabilities)
- **Fast verification:** ~3x faster than ECDSA
- **Small signatures:** 64 bytes vs 72+ for ECDSA
- **Strong security:** 128-bit security level
- **Wide support:** Implemented in every major language

Alternatives considered:
- **ECDSA:** Requires secure RNG, slower verification
- **RSA:** Larger signatures, slower signing
- **Dilithium (PQC):** Not yet standardized when we started

We're adding ML-DSA (FIPS 204) dual-signing for post-quantum migration.

---

## 4. "What about post-quantum?"

Ed25519 and SHA-256 are vulnerable to large-scale quantum computers. Our migration path:

1. **Dual-signing:** Ed25519 + ML-DSA (FIPS 204) simultaneously
2. **Configurable hash functions:** Migrate to SHA-3 or SHAKE
3. **Versioned event formats:** New profile versions specify PQC algorithms

Timeline: Post-quantum extension planned for 2027, contingent on NIST PQC standardization. Spec is in `docs/CRYPTO_SHREDDING.md` (Section 9.4).

Tradeoff: Dual-signing increases event size by ~2.5KB per event.

---

## 5. "How does this compare to Certificate Transparency?"

Certificate Transparency (CT, RFC 6962) logs TLS certificates in a Merkle tree. Provara shares CT's append-only design and Merkle verification but differs in:

| Feature | Certificate Transparency | Provara |
|---------|-------------------------|---------|
| **Scope** | TLS certificates only | Any structured event |
| **Trust model** | Global log operator | Self-sovereign (you control your vault) |
| **Ordering** | Global total order | Per-actor causal chains |
| **Events** | Certificates only | Any JSON payload |

Provara is "CT for arbitrary events with self-sovereign trust."

---

## 6. "What about GDPR right-to-erasure?"

Provara supports crypto-shredding for GDPR Article 17 compliance:

1. Events are encrypted with AES-256-GCM at write time
2. To erase, you destroy the encryption key
3. Ciphertext remains in the log (preserving hash chain integrity)
4. Content is cryptographically unrecoverable

This is the same approach as VCP (draft-kamimura-scitt-vcp-01). Spec is in `docs/CRYPTO_SHREDDING.md`.

Tradeoff: Metadata (event type, actor, timestamp) remains visible. For full erasure, you'd need to encrypt metadata too.

---

## 7. "Why not COSE/CBOR like SCITT?"

SCITT (IETF Working Group) uses COSE/CBOR for supply chain transparency. We considered it but chose JSON because:

- **Human readability:** NDJSON is readable in any text editor (50-year horizon goal)
- **Web compatibility:** JSON is native to browsers and JavaScript
- **Simplicity:** No CBOR decoding required for basic inspection

Tradeoff: JSON is larger than CBOR (~20-30% overhead). For bandwidth-constrained environments, we may add CBOR support.

SCITT compatibility: Provara implements SCITT Phase 1 event types (`SIGNED_STATEMENT`, `RECEIPT`) and export formats.

---

## 8. "How does it handle key compromise?"

Key rotation uses a two-event model:

1. **KEY_REVOCATION:** Signed by the compromised key, sets `trust_boundary_event_id` (last trusted event)
2. **KEY_PROMOTION:** Signed by a surviving trusted authority (quorum key or multi-sig), promotes new key

The compromised key cannot authorize its own replacement. This is similar to certificate revocation in PKI.

Best practices:
- Store root key offline (HSM, YubiKey)
- Use quorum keys for recovery (multi-location storage)
- Rotate keys annually or on personnel changes

---

## 9. "What's the performance like?"

Benchmarks (AMD Ryzen 7 7700X, Python 3.12):

| Operation | Events | Time | Throughput | Memory |
|-----------|--------|------|------------|--------|
| Vault creation | 100K | 0.58s | 171K evt/s | — |
| Chain verification | 100K | 0.53s | 188K evt/s | — |
| Streaming reducer | 100K | 1.96s | 51K evt/s | 56 MB |
| Full reducer | 100K | 157s | 635 evt/s | 279 MB |
| Checkpoint resume | 100K | 1.50s | 67K evt/s | — |

The streaming reducer (v1) is 80x faster than the full reducer (v0) at 100K events. Full results in `tools/benchmarks/results.json`.

Tradeoff: Streaming reducer is read-once (can't seek). Full reducer supports random access but uses O(n) memory.

---

## 10. "Why should I trust this?"

You shouldn't trust us—you should verify:

1. **Open source:** All code is Apache 2.0 on GitHub
2. **Test coverage:** 495 passing tests (unit, integration, compliance, fuzzing)
3. **Cross-language validation:** Three implementations (Python, Rust, TypeScript) validated against test vectors
4. **Formal verification:** TLA+ model proves key invariants (chain integrity, signature validity, determinism)
5. **Standards track:** IETF Internet-Draft submitted for community review
6. **No dependencies:** One external dep (`cryptography`), no phone-home, no telemetry

The protocol spec is frozen in `PROTOCOL_PROFILE.txt`. Changes require community consensus.

---

## 11. "What's the catch? What am I missing?"

Honest tradeoffs:

1. **No encryption at rest:** Provara prioritizes verifiability over confidentiality. Layer encryption (VeraCrypt, encrypted filesystem) if needed.
2. **No built-in backup:** Availability is user responsibility. Use the backup scripts or your own solution.
3. **No query language:** Events are append-only with simple filtering. For complex queries, export to SQLite.
4. **Key management is hard:** If you lose your keys, the vault is read-only forever. Use HSMs and quorum keys.
5. **Not a blockchain:** If you need decentralized consensus, look elsewhere.

---

## 12. "How do I get started?"

```bash
# Install
pip install provara-protocol

# Create a vault
provara init my-vault

# Append an event
provara append my-vault \
  --type OBSERVATION \
  --data '{"event":"test"}' \
  --keyfile my-vault/identity/private_keys.json

# Verify integrity
provara verify my-vault
```

Or try the [browser playground](https://provara-protocol.github.io/provara/)—zero install, runs entirely in the browser.

---

*This FAQ is part of Provara v1.0. For additional questions, open a GitHub issue or join the discussion on HN.*
