# Reddit Launch Posts

**Date:** 2026-02-18  
**Target Subreddits:** r/programming, r/netsec, r/cryptography

---

## r/programming

### Title
**Show HN: Provara – Cryptographic event logs for AI agent memory (51K events/s)**

### Body

I've been working on Provara, a protocol for append-only cryptographic event logs. Think of it as a tamper-evident audit trail that AI agents or distributed systems can use for verifiable memory.

**The problem:** AI agents store memory in databases controlled by vendors, logs that can be silently modified, or proprietary formats that become unreadable when companies fail.

**How it works:** Every event is signed with Ed25519, linked via SHA-256 hash chains, and sealed with Merkle trees. Events are stored as plain text NDJSON—open them with any text editor in 2076.

**Performance:**
- Vault creation: 171K events/second
- Chain verification: 188K events/second
- Streaming reducer: 51K events/second (bounded at 56MB memory)

**Tech stack:**
- Python reference implementation (495 tests)
- Rust and TypeScript ports
- RFC 8785 canonical JSON for cross-platform determinism
- IETF Internet-Draft submitted

**Try it:**
```bash
pip install provara-protocol
provara init my-vault
provara verify my-vault
```

**Links:**
- [GitHub](https://github.com/provara-protocol/provara)
- [Browser Playground](https://provara-protocol.github.io/provara/)
- [IETF Draft](https://datatracker.ietf.org/doc/draft-hunt-provara-protocol/)

Happy to answer questions about the protocol design, cryptographic choices, or performance tradeoffs!

---

## r/netsec

### Title
**Provara: Tamper-evident cryptographic audit logs with Ed25519 signatures and Merkle tree integrity**

### Body

Provara is a protocol for append-only cryptographic event logs designed for tamper-evident audit trails. Unlike databases with audit logging (which rely on trusting the operator), Provara provides cryptographic proof that the log hasn't been modified.

**Cryptographic stack:**
- Ed25519 signatures (RFC 8032) — deterministic, no RNG required
- SHA-256 hash chains (FIPS 180-4) — per-actor causal chains
- Merkle trees — integrity verification for all vault files
- RFC 8785 canonical JSON — byte-identical serialization across platforms

**Security properties:**
- Tamper evidence: Any modification breaks the hash chain
- Non-repudiation: Events are signed by their author
- Forward integrity: Compromised keys can't authorize their own replacement
- Crypto-shredding: GDPR Article 17 compliance via key destruction

**Threat model:** We use STRIDE. Full analysis in `docs/THREAT_MODEL.md`. Key findings:
- Spoofing: Mitigated by Ed25519 (residual: key theft)
- Tampering: Mitigated by signatures + chains + Merkle trees
- Repudiation: Mitigated by cryptographic binding

**Verification:**
```bash
provara verify my-vault
# PASS: All 17 integrity checks passed.
```

**Spec:**
- [Protocol Profile](https://github.com/provara-protocol/provara/blob/main/PROTOCOL_PROFILE.txt) (frozen)
- [IETF Internet-Draft](https://datatracker.ietf.org/doc/draft-hunt-provara-protocol/)

Questions about the crypto design or threat model welcome.

---

## r/cryptography

### Title
**Designing a cryptographic event log protocol: Ed25519, SHA-256, and per-actor causal chains (IETF I-D submitted)**

### Body

I'd like to share the design of Provara, a cryptographic event log protocol we've submitted as an IETF Internet-Draft. I'm particularly interested in feedback on the cryptographic choices and whether we've missed any attack vectors.

**Design decisions:**

1. **Ed25519 over ECDSA:** Deterministic signatures eliminate RNG failures (no nonce reuse vulnerabilities). 128-bit security level, fast verification.

2. **Per-actor causal chains:** Unlike blockchains (global ordering), we maintain separate chains per actor via `prev_event_hash`. Enables concurrency without coordination. Hash chain is O(n) per actor, not O(n²) globally.

3. **RFC 8785 canonical JSON:** Ensures byte-identical serialization across implementations. Critical for cross-platform verification.

4. **Merkle tree over files:** Not just events—all vault files are included. Provides quick integrity checks without replaying the entire chain.

5. **Crypto-shredding for GDPR:** Events encrypted with AES-256-GCM. Destroy the key = content unrecoverable. Ciphertext remains (preserving hash chain). Same approach as VCP (draft-kamimura-scitt-vcp-01).

**Open questions:**

1. **Post-quantum migration:** We're planning ML-DSA dual-signing. Any experience with hybrid classical/PQC signatures?

2. **Key rotation:** Current design uses two-event model (KEY_REVOCATION + KEY_PROMOTION). The compromised key can't authorize its own replacement. Is this sufficient?

3. **Canonical JSON edge cases:** RFC 8785 is clear, but we've found ambiguities in number encoding (floats vs decimals). How do other implementations handle this?

**Spec:**
- [IETF Draft](https://datatracker.ietf.org/doc/draft-hunt-provara-protocol/)
- [Protocol Profile](https://github.com/provara-protocol/provara/blob/main/PROTOCOL_PROFILE.txt)
- [Threat Model](https://github.com/provara-protocol/provara/blob/main/docs/THREAT_MODEL.md)

**Implementation:**
- Python (reference, 495 tests)
- Rust (20 tests)
- TypeScript (browser playground)

All validated against cross-language test vectors.

Would appreciate any cryptanalysis or design feedback!

---

## Posting Guidelines

### Timing

| Subreddit | Best Time (PT) | Day |
|-----------|----------------|-----|
| r/programming | 11:00 AM - 1:00 PM | Tuesday-Thursday |
| r/netsec | 10:00 AM - 12:00 PM | Wednesday |
| r/cryptography | 2:00 PM - 4:00 PM | Thursday |

### Engagement

1. **Reply to all comments** in first 2 hours
2. **Be honest about tradeoffs** — don't oversell
3. **Link to benchmarks** when discussing performance
4. **Acknowledge limitations** — builds credibility

### Rules Compliance

- **r/programming:** No self-promotion without substantial discussion
- **r/netsec:** Must be security-related (tamper evidence qualifies)
- **r/cryptography:** Technical discussion required (design decisions post)

### Cross-Posting

After posting to r/programming, cross-post to:
- r/opensource
- r/artificial
- r/privacy

---

## Follow-up Comments

### Comment to Add (All Subreddits)

> **Performance details for those asking:**
> 
> Benchmarks run on AMD Ryzen 7 7700X, Python 3.12. Full results in [`tools/benchmarks/results.json`](https://github.com/provara-protocol/provara/tree/main/tools/benchmarks).
> 
> The streaming reducer (v1) is 80x faster than the full reducer (v0) at 100K events. Memory is bounded at 56MB vs 279MB for the full reducer.
> 
> Happy to explain the optimization if anyone's interested!

### Comment for r/cryptography

> **On post-quantum:**
> 
> We're planning ML-DSA (FIPS 204) dual-signing. Events would have both Ed25519 and ML-DSA signatures. Overhead is ~2.5KB per event.
> 
> Timeline: 2027, contingent on NIST PQC standardization. Spec draft is in `docs/CRYPTO_SHREDDING.md` (Section 9.4).
> 
> If anyone has experience with hybrid classical/PQC implementations, I'd love to hear about pitfalls.

---

*This Reddit content is part of Provara v1.0 launch materials. For media inquiries, contact press@provara.dev.*
