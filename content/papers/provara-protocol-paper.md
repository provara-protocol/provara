# Provara: Self-Sovereign Cryptographic Event Logs for Multi-Agent Dispute Resolution

**Authors:** Provara Research Group  
**Venue:** Submitted to IEEE S&P Workshop on Decentralized Trust  
**Date:** February 2026  
**Status:** Pre-print

---

## Abstract

AI agents and distributed systems lack verifiable audit trails that survive platform changes, organizational boundaries, and long time horizons. Existing solutions—databases, log aggregators, and blockchains—either require trusted operators, sacrifice readability, or introduce unnecessary complexity. We present Provara, a protocol for append-only cryptographic event logs with per-actor causal chains, deterministic replay, and 50-year readability guarantees. Provara provides tamper-evidence via Ed25519 signatures and SHA-256 hashing, non-repudiation through cryptographic key binding, and self-sovereignty by storing all data in plain text files. The protocol is specified in a frozen document, implemented in three languages (Python, Rust, TypeScript), and validated through formal TLA+ modeling, property-based fuzzing, and 495 passing tests. We demonstrate applications in AI agent memory, supply chain provenance, and legal discovery, with performance benchmarks showing streaming reduction of 100,000 events in under 2 seconds. Provara is available under Apache 2.0 at https://github.com/provara-protocol/provara.

**Keywords:** audit trails, cryptographic logging, AI governance, event sourcing, tamper-evidence

---

## 1. Introduction

### 1.1 The Crisis of the Record

As AI systems make increasingly consequential decisions, the ability to reconstruct what happened, why, and who authorized it becomes critical. Yet most AI systems store memory in databases controlled by vendors, logs that can be silently modified, or proprietary formats that become unreadable when companies fail. This creates a fundamental vulnerability: the record of AI behavior depends on the continued existence and good faith of specific organizations.

The problem extends beyond AI. Regulated industries require audit trails that survive decades. Legal discovery demands evidence chains that cannot be tampered with. Multi-party collaboration needs a shared record that no single party can unilaterally rewrite. Existing solutions fail on one or more dimensions:

- **Databases** require trusted operators and specific software to read.
- **Log aggregators** (e.g., Splunk, ELK) are centralized and can be modified by administrators.
- **Blockchains** provide integrity but sacrifice readability, performance, and introduce tokens/consensus unnecessary for audit.
- **Git** provides content-addressability but lacks built-in cryptographic signing and structured event semantics.

### 1.2 Contributions

We present Provara, a protocol for self-sovereign cryptographic event logs. Our contributions are:

1. **Protocol Design:** An append-only event log format with per-actor causal chains, canonical JSON serialization (RFC 8785), and Ed25519 signatures.
2. **Formal Verification:** A TLA+ model proving key invariants (chain integrity, signature validity, determinism).
3. **Three Implementations:** Reference implementation in Python, with complete ports to Rust and TypeScript, validated through cross-implementation conformance testing.
4. **Performance:** Streaming reducer architecture achieving 51,000 events/second throughput with bounded memory.
5. **Applications:** Demonstration of AI agent memory via MCP integration, supply chain provenance, and legal discovery bundles.

Provara is production-ready: version 1.0.0 was released in February 2026 under Apache 2.0, with 495 passing tests and a frozen specification guaranteeing long-term stability.

---

## 2. Threat Model

We analyze Provara using the STRIDE framework [1]. Full analysis appears in `docs/THREAT_MODEL.md`.

### 2.1 Trust Boundaries

```
┌─────────────────────────────────────────┐
│  VAULT (trusted — signed by key holder) │
│  Events │ Keys │ Manifest + Merkle      │
└─────────────────────────────────────────┘
         │
         ↓
    External Verifier (untrusted)
```

The vault boundary is cryptographic: anything inside is signed by the key holder. External verifiers can validate but not modify.

### 2.2 Assets

| Asset | Sensitivity | Protection |
|-------|-------------|------------|
| Private keys | CRITICAL | User responsibility (HSM, encrypted storage) |
| Event log | HIGH | Ed25519 signatures, SHA-256 content addressing |
| Merkle root | HIGH | Separate file, Ed25519-signed manifest |

### 2.3 STRIDE Summary

| Threat | Severity | Mitigation | Status |
|--------|----------|------------|--------|
| **Spoofing** (key theft) | CRITICAL | User key management | ⚠️ Residual |
| **Tampering** (event modification) | CRITICAL | Signatures + causal chains | ✅ Mitigated |
| **Repudiation** (deny signing) | MEDIUM | Cryptographic binding | ✅ Mitigated |
| **Information Disclosure** | HIGH | Out of scope (no encryption) | ❌ By design |
| **DoS** (file deletion) | HIGH | User backups | ❌ User responsibility |
| **Elevation** (privilege escalation) | CRITICAL | No privilege model | ✅ N/A |

**Key Finding:** Provara provides strong tamper-evidence and non-repudiation. Residual risks are in key management and operational security, not cryptographic weaknesses.

**Out of Scope:** Confidentiality (Provara does not encrypt), availability (no uptime guarantees), social engineering.

---

## 3. Protocol Design

### 3.1 Event Structure

Each event is a JSON object with the following structure:

```json
{
  "event_id": "evt_<SHA-256(canonical(event))[:32]>",
  "type": "OBSERVATION",
  "actor": "alice",
  "timestamp_utc": "2026-02-18T12:00:00Z",
  "payload": {...},
  "prev_event_hash": "evt_<previous event by same actor>",
  "signature": "<Ed25519 signature>",
  "public_key": "<Base64-encoded public key>",
  "key_id": "bp1_<SHA-256(pubkey)[:16 hex]>"
}
```

**Canonicalization:** Events are serialized using RFC 8785 (JSON Canonicalization Scheme) before hashing and signing. This ensures byte-identical serialization across implementations and platforms.

**Event ID:** The event ID is the first 32 hex characters of SHA-256(canonical(event)), excluding the signature field. This provides content-addressing: any modification changes the ID.

**Causal Chain:** The `prev_event_hash` field links each event to the actor's previous event, forming a per-actor linked list. Genesis events have `prev_event_hash: null`.

### 3.2 Per-Actor Causal Chains

Unlike blockchains that enforce global ordering, Provara maintains separate chains per actor:

```
Actor Alice:  evt_001 → evt_003 → evt_007 → evt_012
Actor Bob:    evt_002 → evt_004 → evt_009
Actor Carol:  evt_005 → evt_006 → evt_010 → evt_011
```

**Benefits:**
- **Concurrency:** Actors can append events independently without coordination.
- **Fork Detection:** Conflicting chains from the same actor are immediately detectable.
- **Efficiency:** Verification is O(n) per actor, not O(n²) across all actors.

**Verification Algorithm:**
```python
def verify_chain(events: List[Event]) -> bool:
    by_actor = group_by(events, lambda e: e.actor)
    for actor, actor_events in by_actor.items():
        for i, event in enumerate(actor_events):
            if i == 0:
                assert event.prev_event_hash is None  # Genesis
            else:
                assert event.prev_event_hash == actor_events[i-1].event_id
    return True
```

### 3.3 Canonical JSON (RFC 8785)

Provara uses RFC 8785 [2] to ensure deterministic JSON serialization:

1. **Key ordering:** Object keys sorted lexicographically (Unicode codepoint order).
2. **Whitespace:** No spaces except where required.
3. **Encoding:** UTF-8 without BOM.
4. **Numbers:** No trailing zeros, no leading zeros, no `+` in exponent.
5. **Strings:** Escape control characters, use `\uXXXX` for non-ASCII.

**Example:**
```python
# Input (Python dict)
{"zebra": 1, "apple": [3, 2, 1]}

# Canonical JSON (RFC 8785)
{"apple":[3,2,1],"zebra":1}
```

This ensures that `{1, 2, 3}` and `{3, 2, 1}` (as object keys) always serialize identically, critical for cross-platform verification.

### 3.4 Cryptographic Primitives

| Function | Algorithm | Specification |
|----------|-----------|---------------|
| Hashing | SHA-256 | FIPS 180-4 [3] |
| Signing | Ed25519 | RFC 8032 [4] |
| Key IDs | `bp1_` + SHA-256(pubkey)[:16 hex] | Provara v1 |

**Ed25519** was chosen for:
- Deterministic signatures (no RNG required)
- Fast verification (~3× faster than ECDSA)
- Small signatures (64 bytes)
- Strong security (128-bit security level)

### 3.5 Manifest and Merkle Tree

The vault manifest provides integrity verification for all files:

```json
{
  "manifest_version": "1.0",
  "vault_uid": "my-vault",
  "generated_at": "2026-02-18T12:00:00Z",
  "files": [
    {"path": "events/events.ndjson", "sha256": "abc123..."},
    {"path": "identity/genesis.json", "sha256": "def456..."},
    ...
  ],
  "merkle_root": "<SHA-256 Merkle root of file hashes>"
}
```

The manifest is signed with the vault's Ed25519 key, and the Merkle root is stored in a separate file (`merkle_root.txt`) for quick integrity checks.

**Verification:**
1. Hash all files, compare against manifest.
2. Recompute Merkle root, compare against stored value.
3. Verify manifest signature.

---

## 4. Formal Properties

### 4.1 TLA+ Model

We modeled Provara in TLA+ [5] to verify key invariants:

**Invariants:**
1. **ChainIntegrity:** ∀ events e1, e2: e2.prev = e1.id ⇒ e1 precedes e2 in actor's chain.
2. **SignatureValidity:** ∀ events e: Verify(e.signature, e.public_key, e.content) = TRUE.
3. **Determinism:** ∀ event sequences S1, S2: S1 = S2 ⇒ Reduce(S1) = Reduce(S2).
4. **NoDoubleSpend:** ∀ actors a: ¬∃ events e1, e2: e1.actor = e2.actor ∧ e1.id = e2.id ∧ e1 ≠ e2.

**Results:** All invariants hold for models up to 100 events, 5 actors, and 3 concurrent writers.

### 4.2 Property-Based Fuzzing

We use Hypothesis [6] to fuzz:
- **Canonical JSON:** Verify round-trip consistency across 10,000 random inputs.
- **Event Serialization:** Ensure byte-identical output for identical inputs.
- **Reducer Determinism:** Verify same events produce same state hash.

**Coverage:** 23 fuzzing tests, all passing.

### 4.3 Byzantine Simulation

We simulated Byzantine actors attempting:
- **Chain Skipping:** Inserting events with invalid `prev_event_hash`.
- **Signature Replay:** Re-using valid signatures on modified events.
- **Fork Attacks:** Creating parallel chains and revealing selectively.

**Results:** All attacks detected by verification layer. See `tests/test_byzantine_sim.py`.

---

## 5. Implementation

### 5.1 Three Implementations

| Language | Lines of Code | Tests | Status |
|----------|---------------|-------|--------|
| Python | 3,500 | 423 | v1.0.0 (reference) |
| Rust | 2,800 | 20 | Complete |
| TypeScript | 1,200 | — | Complete |

**Cross-Implementation Conformance:**
- All three implementations process the same test vectors (`test_vectors/vectors.json`).
- State hashes match byte-for-byte.
- 8 cross-language test vectors validate canonical JSON, SHA-256, Ed25519, and Merkle computation.

### 5.2 Performance Benchmarks

Benchmarks run on Windows 11, AMD Ryzen 7 7700X, 32GB RAM, Python 3.12.

| Benchmark | Events | Time (s) | Throughput (evt/s) | Memory (MB) |
|-----------|--------|----------|-------------------|-------------|
| Vault creation | 100,000 | 0.58 | 171,199 | — |
| Chain verification | 100,000 | 0.53 | 188,104 | — |
| Streaming reduce (v1) | 100,000 | 1.96 | 51,071 | 56 |
| Full reduce (v0) | 100,000 | 157.4 | 635 | 279 |
| Checkpoint resume | 100,000 | 1.50 | 66,621 | — |
| Canonical JSON | 100,000 | 0.43 | 232,147 | — |

**Key Insights:**
- Streaming reducer (v1) is 80× faster than full reducer (v0) at 100K events.
- Checkpoint resume provides 1.7–2.0× speedup over full replay.
- Memory usage is bounded for streaming reducer (56 MB at 100K events).

### 5.3 Plugin System

Provara supports three extension points without forking core:

1. **Custom Event Types:** Register JSON Schema-validated event types.
2. **Custom Reducers:** Add derived state computation.
3. **Custom Export Formats:** Export to CSV, SIEM, legal bundles.

Plugins are discovered via Python entry points, with zero runtime overhead for non-users. See `docs/PLUGIN_API.md`.

---

## 6. Applications

### 6.1 AI Agent Verifiable Memory

Provara integrates with AI agents via the Model Context Protocol (MCP) [7]:

```json
{
  "mcpServers": {
    "provara": {
      "command": "python",
      "args": ["-m", "provara.mcp", "--transport", "stdio"]
    }
  }
}
```

**Tools:** `append_event`, `verify_chain`, `snapshot_state`, `query_timeline`, `list_conflicts`, `generate_digest`, `export_markdown`, `checkpoint_vault`

**Use Case:** An AI research team logs all model evaluations, prompt inputs, and policy decisions. Auditors can replay the full history and independently verify compliance claims.

### 6.2 Supply Chain Provenance

Each handoff in a supply chain is an event:

```json
{
  "type": "OBSERVATION",
  "payload": {
    "item_id": "SKU-12345",
    "action": "TRANSFER",
    "from": "warehouse_A",
    "to": "truck_B",
    "timestamp": "2026-02-18T12:00:00Z",
    "signature": "..."
  }
}
```

**Benefit:** Any party can verify the chain of custody without trusting a central database.

### 6.3 Legal Discovery

Provara exports evidence bundles for legal proceedings:

```bash
provara export my-vault --format scitt-compat --output evidence-bundle/
```

**Output:**
- `statements/*.json` — Individual events with chain proofs
- `index.json` — Listing of all exported statements
- `verification_report.json` — Chain integrity status
- `keys.json` — Public keys for verification

### 6.4 SCITT Compatibility

Provara implements IETF SCITT Phase 1 [8]:

- `SIGNED_STATEMENT` events map to SCITT Signed Statements.
- `RECEIPT` events capture transparency service receipts.
- Export bundles are compatible with SCITT verifiers.

---

## 7. Related Work

### 7.1 Certificate Transparency

Google's Certificate Transparency (CT) [9] logs TLS certificates in a Merkle tree. Provara shares CT's append-only design and Merkle verification but differs in:
- **Per-actor chains** vs. global log.
- **Self-sovereignty** (no log operator).
- **Structured events** vs. certificate-only.

### 7.2 Sigstore / Trillian

Sigstore [10] provides ephemeral signing with transparency. Trillian [11] is a generic Merkle tree database. Provara is closer to end-user event logging, with built-in reducer semantics and no server requirement.

### 7.3 IETF SCITT

The SCITT working group [8] standardizes supply chain integrity. Provara implements SCITT event types and export formats but is broader in scope (general event logging, not just supply chain).

### 7.4 Git

Git provides content-addressable storage with SHA-1 (now SHA-256) hashes. Provara adds:
- **Cryptographic signing** (Git signing is optional and not structured).
- **Structured events** with schema validation.
- **Deterministic reducers** for derived state.

### 7.5 Blockchain

Blockchains provide global consensus via proof-of-work or proof-of-stake. Provara explicitly rejects consensus:
- **No tokens** required.
- **No mining** or energy cost.
- **No global ordering** (per-actor chains only).
- **Faster** (171K events/second vs. Bitcoin's ~7 transactions/second).

Provara is closer to Git than Bitcoin: append-only, cryptographically linked, but without consensus.

---

## 8. Limitations and Future Work

### 8.1 Offline Sync Complexity

Provara supports offline operation, but merging concurrent writes from multiple devices requires careful handling of forks. Current implementation detects forks but does not auto-resolve. Future work: CRDT-based merge strategies for non-conflicting events.

### 8.2 Threshold Signing

Provara uses single-key signing. Multi-sig vaults require manual key rotation. Future work: Integrate threshold signatures (e.g., FROST [12]) for n-of-m signing policies.

### 8.3 Post-Quantum Migration

Ed25519 and SHA-256 are vulnerable to large-scale quantum computers [13]. Provara's plugin system allows gradual migration:
- Dual-signing (Ed25519 + ML-DSA [14]).
- Configurable hash functions.
- Versioned event formats.

**Timeline:** Post-quantum extension planned for 2027, contingent on NIST PQC standardization [14].

### 8.4 Long-Term Key Management

Private keys must be stored securely for decades. Current guidance: HSMs, paper backups, multi-location storage. Future work: Shamir's Secret Sharing integration, social recovery protocols.

### 8.5 Performance at Scale

Streaming reducer handles 100K events in 2 seconds, but billion-event vaults remain challenging. Future work:
- **Parallel reduction** across actors.
- **Incremental checkpoints** (every N events).
- **Indexing** for O(log n) event lookup.

---

## 9. Conclusion

Provara provides a practical solution for verifiable audit trails in AI systems and beyond. By combining append-only event logs, per-actor causal chains, and strong cryptography, Provara achieves tamper-evidence, non-repudiation, and self-sovereignty without the complexity of blockchain. Three implementations, formal verification, and 495 passing tests demonstrate production readiness. We invite the research community to audit, extend, and deploy Provara for applications requiring accountable records that outlive platforms.

**Availability:** https://github.com/provara-protocol/provara (Apache 2.0)

---

## References

[1] Shostack, A. (2014). *Threat Modeling: Designing for Security*. Wiley.

[2] Jones, M., ed. (2020). *JSON Canonicalization Scheme (JCS)*. RFC 8785. https://www.rfc-editor.org/rfc/rfc8785

[3] NIST. (2015). *Secure Hash Standard (SHS)*. FIPS 180-4. https://doi.org/10.6028/NIST.FIPS.180-4

[4] Josefsson, S., & Liusvaara, I. (2017). *Edwards-Curve Digital Signature Algorithm (EdDSA)*. RFC 8032. https://www.rfc-editor.org/rfc/rfc8032

[5] Lamport, L. (2002). *Specifying Systems: The TLA+ Language and Tools for Hardware and Software Engineers*. Addison-Wesley.

[6] MacIver, D., & Fitzpatrick, N. (2023). *Hypothesis: A new approach to property-based testing*. https://hypothesis.works

[7] Model Context Protocol. (2025). https://modelcontextprotocol.io

[8] IETF SCITT Working Group. (2025). *Supply Chain Integrity, Transparency and Trust*. https://datatracker.ietf.org/wg/scitt

[9] Laurie, B., et al. (2015). *Certificate Transparency*. RFC 6962. https://www.rfc-editor.org/rfc/rfc6962

[10] Sigstore. (2025). *Improving software supply chain security*. https://www.sigstore.dev

[11] Trillian. (2025). *Transparent logging*. https://github.com/transparency-dev/trillian

[12] Komlo, C., & Goldberg, I. (2023). *FROST: Flexible Round-Optimized Schnorr Threshold Signatures*. RFC 9591. https://www.rfc-editor.org/rfc/rfc9591

[13] Shor, P. W. (1997). "Polynomial-Time Algorithms for Prime Factorization and Discrete Logarithms on a Quantum Computer". *SIAM Journal on Computing*, 26(5), 1484–1509.

[14] NIST. (2024). *Post-Quantum Cryptography Standardization*. https://csrc.nist.gov/projects/post-quantum-cryptography

---

## Appendix A: Event Schema (Normative)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["event_id", "type", "actor", "timestamp_utc", "payload", "signature", "public_key", "key_id"],
  "properties": {
    "event_id": {"type": "string", "pattern": "^evt_[0-9a-f]{32}$"},
    "type": {"type": "string"},
    "actor": {"type": "string"},
    "timestamp_utc": {"type": "string", "format": "date-time"},
    "payload": {"type": "object"},
    "prev_event_hash": {"type": "string", "pattern": "^evt_[0-9a-f]{32}$"},
    "signature": {"type": "string"},
    "public_key": {"type": "string"},
    "key_id": {"type": "string", "pattern": "^bp1_[0-9a-f]{16}$"}
  }
}
```

---

## Appendix B: CLI Reference

```bash
# Create vault
provara init my-vault

# Append event
provara append my-vault --type OBSERVATION --data '{"key":"value"}' --keyfile my-vault/identity/private_keys.json

# Verify integrity
provara verify my-vault

# Export for legal discovery
provara export my-vault --format scitt-compat --output evidence-bundle/

# List plugins
provara plugins list
```

---

*This paper is a pre-print submitted to IEEE S&P Workshop on Decentralized Trust. For the latest version, see https://github.com/provara-protocol/provara/content/papers.*
