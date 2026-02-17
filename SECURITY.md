# Security Policy

## Reporting Vulnerabilities

**Do not open a public GitHub issue for security vulnerabilities.**

Report vulnerabilities privately via GitHub's security advisory workflow:
https://github.com/provara-protocol/provara/security/advisories/new

We aim to acknowledge reports within 48 hours and provide a fix or mitigation
within 14 days for critical issues.

---

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x | ✅ Yes |
| 0.1.x | ❌ No (deprecated) |

Profile A (`PROVARA-1.0_PROFILE_A`) is the only currently supported profile.

---

## Threat Model

Provara provides **tamper evidence**, not encryption or access control.

### What Provara Guarantees

| Property | Mechanism |
|----------|-----------|
| **Append-only** | Events are never deleted. No API exists to remove or modify events. |
| **Tamper-evident** | Any modification to an event breaks its Ed25519 signature. |
| **Causal chain integrity** | Inserting, reordering, or removing an event breaks `prev_event_hash` for all subsequent events. |
| **Deterministic replay** | Any auditor can replay the full event log and arrive at the byte-identical `state_hash`. |
| **Key binding** | Every event is cryptographically bound to a specific Ed25519 key via `key_id`. |
| **Content addressing** | `event_id` is derived from event content — identical content always produces the same ID. |

### What Provara Does NOT Guarantee

| Property | Notes |
|----------|-------|
| **Confidentiality** | Events are stored as plaintext NDJSON. Encryption at rest is a planned extension (not in Profile A). |
| **Access control** | Provara does not enforce who can read or append events. Access control is the caller's responsibility. |
| **Availability** | Local-first. No replication or clustering in the core protocol. |
| **Key secrecy** | The private key must be kept secret by the vault owner. Provara does not manage private key storage. |

---

## Known Attack Scenarios

### Replay Attack
**Description:** An attacker records valid events and replays them in a different context.

**Mitigation:** Events contain `actor`, `timestamp`, and `prev_event_hash`. Replayed events fail causal chain validation unless they hash-chain correctly into the target vault's history.

**Residual risk:** A full vault copy is indistinguishable from the original — this is by design (verifiability requires reproducibility). Guard physical access.

### Chain Truncation
**Description:** An attacker discards recent events, presenting an older state as current.

**Mitigation:** Provara detects gaps in the causal chain but cannot detect truncation at the *tail* (after the last event). Use signed checkpoints and compare `state_hash` with trusted peers.

**Residual risk:** Out-of-band state comparison (e.g., epoch anchors to a transparency log) is recommended for high-assurance deployments.

### Key Compromise Recovery
**Description:** The signing key is compromised. Can an attacker forge historical events?

**Mitigation:** Existing events retain their original signatures. A compromised key cannot retroactively re-sign historical events without breaking the causal chain. Use `KEY_REVOCATION` + `KEY_PROMOTION` to establish a trust boundary.

**Residual risk:** Events signed before revocation remain valid (they were legitimately signed at the time).

### Time Manipulation / Backdating
**Description:** An attacker with write access creates events with false timestamps.

**Mitigation:** Timestamps are informational, not cryptographically enforced. Causal chain enforces ordering within an actor's chain but not wall-clock accuracy.

**Residual risk:** For high-assurance use cases, include a trusted timestamp authority signature in the event payload.

### Storage-Layer Tampering
**Description:** An attacker with filesystem access modifies or deletes events.

**Mitigation:** Ed25519 signatures bind each event to its content (`PROVARA_E003`). Deletion breaks causal chain (`PROVARA_E002`, `PROVARA_E006`). The compliance verifier detects both.

### Fork-and-Discard Attack
**Description:** An attacker creates a valid fork, records favorable events, then presents the original.

**Mitigation:** Detecting forks requires comparing chains with a trusted peer or publishing epoch-anchors to a third party (Rekor, transparency log). Single-node vaults are vulnerable without external anchoring.

### DoS via Large Events
**Description:** Extremely large events exhaust disk space or slow verification.

**Mitigation:** Provara does not enforce per-event size limits at the protocol layer. Applications SHOULD enforce size limits before calling `append_event`.

### Key ID Collision
**Description:** Two different keys produce the same `bp1_` + 16-hex key ID.

**Probability:** ~2³² vaults needed for a birthday collision — negligible in practice. Always verify the full signature against stored public key bytes, not just the key ID.

---

## Cryptographic Parameters

| Primitive | Specification | Security Level |
|-----------|--------------|----------------|
| SHA-256 | FIPS 180-4 | 128-bit collision |
| Ed25519 | RFC 8032 | ~128-bit |
| Canonical JSON | RFC 8785 | Deterministic |

**Post-quantum:** Ed25519 is not post-quantum secure. A `PROTOCOL_PROFILE_PQ.txt` extension for ML-DSA dual-signing is planned.

---

*Provara Protocol v1.0 | Apache 2.0 | provara.dev*
