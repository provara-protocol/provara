# Provara Threat Model

**Version:** 1.0  
**Date:** 2026-02-17  
**Status:** Living document  
**Owner:** Security working group

---

## Executive Summary

Provara is a tamper-evident event log system designed for 50-year readability and cryptographic integrity. This threat model analyzes Provara using the STRIDE framework across its trust boundaries.

**Key finding:** Provara's core cryptographic design (Ed25519 + SHA-256 + append-only chains) provides strong protection against tampering and spoofing. Primary residual risks are in key management, implementation bugs, and operational security — not cryptographic weaknesses.

**Out of scope:** Confidentiality (Provara does not encrypt data), availability (no uptime guarantees), social engineering attacks.

---

## System Overview

### Trust Boundaries

```
┌─────────────────────────────────────────────────────────────┐
│  VAULT (trusted boundary — signed by key holder)           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Events    │  │   Keys      │  │  Manifest   │        │
│  │  (NDJSON)   │  │  (PEM)      │  │  + Merkle   │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│         ↑                ↑                ↑                 │
│         │                │                │                 │
│  ───────┴────────────────┴────────────────┴──────────────  │
│                     CRYPTOGRAPHIC BOUNDARY                  │
└─────────────────────────────────────────────────────────────┘
         │                │                │
         ↓                ↓                ↓
    External         External         External
    Verifier       Key Holder       Storage
```

### Assets to Protect

| Asset | Sensitivity | Why |
|-------|-------------|-----|
| Private keys | CRITICAL | Compromise = identity takeover |
| Event log | HIGH | Tampering destroys evidentiary value |
| Merkle root | HIGH | Integrity anchor for entire vault |
| Public keys | MEDIUM | Needed for verification, but public |
| Vault files (non-crypto) | LOW | Can be regenerated or replaced |

### Actors

| Actor | Trust Level | Capabilities |
|-------|-------------|--------------|
| **Vault Owner** | Trusted | Full read/write access, holds private keys |
| **External Verifier** | Untrusted | Read-only access, can verify signatures/chains |
| **Network Attacker** | Adversarial | Can observe/modify data in transit (if synced) |
| **Local Attacker** | Adversarial | Can access vault files if storage is compromised |
| **Provara Developers** | Partially Trusted | Write code, but cannot access user keys |

---

## STRIDE Analysis

### 1. SPOOFING (Can an attacker impersonate a key holder?)

| Threat ID | Description | Severity | Mitigation | Status |
|-----------|-------------|----------|------------|--------|
| **SPOOF-01** | Attacker steals private key and signs events as the owner | CRITICAL | Keys stored encrypted at rest; OS keychain integration recommended | ✅ Implemented (user responsibility) |
| **SPOOF-02** | Attacker generates a key with a colliding key ID (`bp1_...`) | CRITICAL | Key ID is 64 bits of SHA-256(pubkey); collision requires 2^32 work minimum | ✅ Cryptographically infeasible |
| **SPOOF-03** | Attacker substitutes public key in vault's `keys.json` | HIGH | Public key registry is part of manifest; Merkle root would not match | ✅ Manifest + Merkle verification |
| **SPOOF-04** | Attacker claims to be Provara "official" vault | MEDIUM | No central authority; users must verify provenance out-of-band | ⚠️ User education needed |

**Residual Risk:** LOW — Cryptographic identity is strong. Primary risk is key theft via malware, phishing, or poor operational security.

---

### 2. TAMPERING (Can an attacker modify the record undetectably?)

| Threat ID | Description | Severity | Mitigation | Status |
|-----------|-------------|----------|------------|--------|
| **TAMPER-01** | Attacker modifies an event's payload | CRITICAL | Event ID is content-addressed; signature would not match | ✅ SHA-256 + Ed25519 |
| **TAMPER-02** | Attacker inserts a new event into the middle of the chain | CRITICAL | Causal chain via `prev_event_hash`; insertion breaks linkage | ✅ Causal chain verification |
| **TAMPER-03** | Attacker deletes events from the log | CRITICAL | Event sequence numbers and chain linkage would show gaps | ✅ Chain verification detects gaps |
| **TAMPER-04** | Attacker replaces entire event log with a forged one | HIGH | Manifest Merkle root would not match; signatures still valid but provenance differs | ✅ Merkle verification + provenance tracking |
| **TAMPER-05** | Attacker modifies vault files (policies, manifest) | HIGH | All files included in Merkle tree; root stored separately | ✅ Manifest + Merkle tree |
| **TAMPER-06** | Attacker performs "equivocation attack" (two different events with same hash) | CRITICAL | SHA-256 collision resistance; no known practical attacks | ✅ Cryptographically secure |
| **TAMPER-07** | Attacker exploits JSON parsing ambiguity (RFC 8785 violations) | MEDIUM | Canonical JSON strictly enforced; test vectors validate | ✅ RFC 8785 + conformance tests |

**Residual Risk:** VERY LOW — Tamper-evidence is Provara's core guarantee. All known attacks require breaking SHA-256 or Ed25519.

---

### 3. REPUDIATION (Can someone deny they signed something?)

| Threat ID | Description | Severity | Mitigation | Status |
|-----------|-------------|----------|------------|--------|
| **REPUD-01** | Key holder claims "that wasn't me" after signing an event | MEDIUM | Signature is cryptographically binding; key holder is responsible for key security | ✅ By design — signature = authorship |
| **REPUD-02** | Key holder claims key was compromised at time of signing | MEDIUM | Key revocation events exist; burden of proof is on key holder to show revocation predates event | ✅ Revocation protocol exists |
| **REPUD-03** | Third party claims signature was forged | LOW | Ed25519 signatures are publicly verifiable; anyone can verify | ✅ Public verification |

**Residual Risk:** LOW — Cryptographic signatures are non-repudiable by design. Social/legal repudiation is out of scope.

---

### 4. INFORMATION DISCLOSURE (Can vault contents leak?)

| Threat ID | Description | Severity | Mitigation | Status |
|-----------|-------------|----------|------------|--------|
| **INFO-01** | Attacker reads vault files from disk | HIGH | **OUT OF SCOPE** — Provara does not encrypt; user must use disk encryption | ❌ Not implemented (by design) |
| **INFO-02** | Attacker intercepts vault during sync | MEDIUM | Sync is optional; users should use encrypted channels (e.g., SSH, HTTPS) | ⚠️ User responsibility |
| **INFO-03** | Metadata leakage (file sizes, timestamps reveal sensitive info) | LOW | **OUT OF SCOPE** — Provara does not hide metadata | ❌ Not implemented |
| **INFO-04** | Memory scraping (attacker reads vault from RAM) | MEDIUM | **OUT OF SCOPE** — Provara does not implement secure memory handling | ❌ Not implemented |

**Residual Risk:** HIGH — But **intentional**. Provara prioritizes integrity over confidentiality. Users who need confidentiality must layer encryption (e.g., VeraCrypt, encrypted filesystem).

**Design Rationale:** From SOUL.md: *"Provara is not truth. It is evidence."* Encryption would prevent third-party verification, undermining Provara's core value proposition.

---

### 5. DENIAL OF SERVICE (Can an attacker make the vault unusable?)

| Threat ID | Description | Severity | Mitigation | Status |
|-----------|-------------|----------|------------|--------|
| **DOS-01** | Attacker deletes or corrupts vault files | HIGH | **OUT OF SCOPE** — Provara does not guarantee availability; user must backup | ❌ Not implemented (user responsibility) |
| **DOS-02** | Attacker floods vault with junk events | MEDIUM | No rate limiting; vault size grows unbounded | ⚠️ User monitoring required |
| **DOS-03** | Attacker creates a "fork bomb" (many conflicting events) | LOW | Reducer handles conflicts; contested namespace isolates them | ✅ Contested namespace |
| **DOS-04** | Attacker exploits performance bottleneck (e.g., O(n²) reducer) | MEDIUM | Checkpoint system reduces replay time; streaming reducer planned | ⚠️ Checkpoint implemented, streaming TODO |
| **DOS-05** | Ransomware encrypts vault files | HIGH | **OUT OF SCOPE** — User must maintain offline backups | ❌ Not implemented (user responsibility) |

**Residual Risk:** MEDIUM — Availability is explicitly a user responsibility (SOUL.md Commitment V: "Sovereignty means nothing if you can't leave"). Provara provides tools; users must operate them.

---

### 6. ELEVATION OF PRIVILEGE (Can an attacker gain unauthorized access?)

| Threat ID | Description | Severity | Mitigation | Status |
|-----------|-------------|----------|------------|--------|
| **ELEV-01** | Attacker escalates from read-only to write access | CRITICAL | Write access requires private key; no privilege escalation path exists | ✅ Cryptographic access control |
| **ELEV-02** | Attacker bypasses key revocation and uses revoked key | HIGH | Revocation events are checked during verification; revoked keys rejected | ✅ Revocation verification |
| **ELEV-03** | Attacker exploits bug in reducer to inject beliefs | MEDIUM | Reducer is pure function; beliefs are deterministic from events | ⚠️ Code review + testing required |
| **ELEV-04** | Attacker uses Provara vault to store malicious payload (e.g., exploit in parser) | LOW | Parser is simple JSON; no code execution paths | ✅ Minimal attack surface |

**Residual Risk:** LOW — No privilege escalation paths identified. Primary risk is implementation bugs.

---

## Out of Scope (Explicitly Not Defended Against)

| Threat | Why Out of Scope | User Mitigation |
|--------|------------------|-----------------|
| **Confidentiality** | Provara prioritizes verifiability over secrecy | Layer encryption (VeraCrypt, encrypted filesystem) |
| **Availability** | Sovereignty requires user-controlled backups | Maintain multiple backups; use RAID, cloud sync |
| **Social Engineering** | No technical control can prevent users from being tricked | User education; multi-sig for high-value vaults |
| **Physical Access Attacks** | If attacker has physical access, all bets are off | Secure hardware; HSM for key storage |
| **Quantum Computing** | Ed25519 and SHA-256 are vulnerable to large-scale quantum computers | Post-quantum extension planned (PROTOCOL_PROFILE_PQ.txt) |
| **Implementation Bugs** | Provara is software; bugs may exist | Code review, fuzzing, audits, bug bounties |

---

## Security Recommendations (Prioritized)

### P0 — Critical (Do Now)

1. **Key management guidance** — Document best practices for key storage (HSM, YubiKey, encrypted storage)
2. **Backup strategy** — Provide explicit backup/restore documentation with testing procedures
3. **Fuzzing harness** — Build fuzzing for canonical JSON parser and event deserialization

### P1 — High (Do This Quarter)

4. **Security audit** — Engage third-party auditor for crypto implementation review
5. **Bug bounty program** — Set up responsible disclosure process with rewards
6. **Property-based tests** — Add Hypothesis tests for reducer invariants

### P2 — Medium (Do This Year)

7. **Post-quantum extension** — Draft PROTOCOL_PROFILE_PQ.txt with ML-DSA dual-signing
8. **Multi-sig vaults** — Support threshold signatures for high-value vaults
9. **Hardware security module integration** — Native YubiKey/HSM support

---

## Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| No encryption at rest | Vault contents are plaintext | Use encrypted filesystem or encrypt sensitive data before storing |
| No built-in backup | User must manage backups | Use `backup_vault.sh`/`.bat` scripts; maintain 3-2-1 backup strategy |
| No rate limiting | Vault can be flooded with events | Monitor vault size; implement application-level rate limiting |
| No multi-sig | Single key = single point of failure | Use quorum keys; store root key offline |
| No quantum resistance | Vulnerable to future quantum computers | Plan for post-quantum migration; monitor NIST PQC standardization |

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-17 | Provara Security Working Group | Initial threat model |

---

## References

- [SOUL.md](./SOUL.md) — Provara's founding commitments
- [PROTOCOL_PROFILE.txt](./PROTOCOL_PROFILE.txt) — Cryptographic specification
- [SECURITY.md](./SECURITY.md) — Vulnerability disclosure process
- [NIST STRIDE Framework](https://csrc.nist.gov/glossary/term/stride)

---

*This document is a living record. If you find a threat we missed, file an issue. If you find a vulnerability, see SECURITY.md for responsible disclosure.*
