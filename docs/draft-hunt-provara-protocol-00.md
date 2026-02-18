# Provara: A Self-Sovereign Cryptographic Event Log Protocol

**Internet-Draft:** draft-hunt-provara-protocol-00  
**Category:** Informational  
**Author:** Hunt Information Systems LLC  
**Date:** February 18, 2026  

---

## Abstract

AI agents and distributed systems lack verifiable audit trails that survive platform changes, organizational boundaries, and long time horizons. Existing solutions—databases, log aggregators, and blockchains—either require trusted operators, sacrifice readability, or introduce unnecessary complexity.

This document specifies Provara, a protocol for append-only cryptographic event logs with per-actor causal chains, deterministic replay, and 50-year readability guarantees. Provara provides tamper-evidence via Ed25519 signatures and SHA-256 hashing, non-repudiation through cryptographic key binding, and self-sovereignty by storing all data in plain text files.

The protocol uses RFC 8785 canonical JSON for cross-platform determinism, per-actor causal chains for concurrency without coordination, and Merkle trees for file integrity. Provara is designed for AI agent memory, supply chain provenance, legal discovery, and any application requiring accountable records that outlive platforms.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Terminology](#2-terminology)
3. [Protocol Overview](#3-protocol-overview)
4. [Event Structure](#4-event-structure)
5. [Cryptographic Operations](#5-cryptographic-operations)
6. [Causal Chain](#6-causal-chain)
7. [Manifest and Integrity](#7-manifest-and-integrity)
8. [Extension Mechanism](#8-extension-mechanism)
9. [Security Considerations](#9-security-considerations)
10. [IANA Considerations](#10-iana-considerations)
11. [References](#11-references)
12. [Appendix A: Event Schema](#appendix-a-event-schema-normative)
13. [Appendix B: CLI Reference](#appendix-b-cli-reference)

---

## 1. Introduction

### 1.1 Problem Statement

As AI systems make increasingly consequential decisions, the ability to reconstruct what happened, why, and who authorized it becomes critical. Yet most AI systems store memory in databases controlled by vendors, logs that can be silently modified, or proprietary formats that become unreadable when companies fail. This creates a fundamental vulnerability: the record of AI behavior depends on the continued existence and good faith of specific organizations.

The problem extends beyond AI. Regulated industries require audit trails that survive decades. Legal discovery demands evidence chains that cannot be tampered with. Multi-party collaboration needs a shared record that no single party can unilaterally rewrite.

Existing solutions fail on one or more dimensions:

- **Databases** require trusted operators and specific software to read.
- **Log aggregators** (e.g., Splunk, ELK) are centralized and can be modified by administrators.
- **Blockchains** provide integrity but sacrifice readability, performance, and introduce tokens and consensus unnecessary for audit.
- **Git** provides content-addressability but lacks built-in cryptographic signing and structured event semantics.

### 1.2 Design Goals

Provara is designed with the following goals:

- **Self-sovereign:** No accounts, no internet required, no vendor lock-in. Identity lives in files, not on servers.
- **Append-only:** Events are never modified or deleted. Corrections are new events that supersede old ones.
- **Tamper-evident:** Any modification to the record is cryptographically detectable.
- **50-year horizon:** JSON, SHA-256, and Ed25519 are industry standards that will remain readable for decades.
- **Deterministic replay:** Given the same event log, any compliant implementation produces byte-identical state.
- **Human-readable:** The event log is NDJSON (newline-delimited JSON), readable with any text editor.

### 1.3 Scope

Provara is:

- A protocol for append-only cryptographic event logs.
- A format for structured events with cryptographic signatures.
- A deterministic reducer for deriving state from events.
- A manifest and Merkle tree for file integrity verification.

Provara is not:

- A blockchain (no consensus, no tokens, no mining).
- An encryption system (confidentiality is out of scope; layer encryption as needed).
- A database (no indexing, no query language; events are append-only).
- A backup system (availability is user responsibility).

---

## 2. Terminology

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they appear in all capitals, as shown here.

**Vault:** A directory containing a compliant event log, identity files, policies, and manifest. Also called a "backpack".

**Event:** An immutable, content-addressed JSON record appended to the event log.

**Actor:** The identity that authored an event, identified by a key ID.

**Chain:** A per-actor linked list of events via prev_event_hash references.

**Manifest:** A JSON file enumerating every vault file with its SHA-256 hash and size.

**Reducer:** A pure function f(events) → state that deterministically produces derived beliefs.

**State hash:** A SHA-256 digest of reducer output, byte-identical across all compliant implementations.

**Merkle root:** A SHA-256 Merkle tree root over all vault files, sealing vault integrity.

**Key ID:** A short identifier for an Ed25519 public key, formatted as "bp1_" followed by 16 hexadecimal characters.

---

## 3. Protocol Overview

### 3.1 Architecture

Provara vaults follow this architecture:

```
                            PROVARA PROTOCOL
                            ================

  +-----------------+       +---------------------+       +------------------+
  |                 |       |                     |       |                  |
  |  EVENTS         |  -->  |  REDUCER            |  -->  |  BELIEF STATE    |
  |  (append-only   |       |  (deterministic,    |       |  (derived view,  |
  |   NDJSON log)   |       |   replayable)       |       |   never merged)  |
  |                 |       |                     |       |                  |
  +-----------------+       +---------------------+       +------------------+
                                                                  |
                                                                  v
                                                          +------------------+
                                                          |  MANIFEST        |
                                                          |  + Merkle Root   |
                                                          |  + Ed25519 Sig   |
                                                          +------------------+

  Events flow in. The reducer processes them deterministically.
  Beliefs emerge. The manifest seals the vault state.

  Same events --> same reducer --> same state hash. Always.
```

### 3.2 Event Lifecycle

The event lifecycle is:

1. **Creation:** An actor creates an event with payload, type, and timestamp.
2. **Canonicalization:** The event is serialized using RFC 8785 canonical JSON.
3. **Signing:** The actor signs the canonical bytes with their Ed25519 private key.
4. **Content addressing:** The event ID is computed as SHA-256 of canonical bytes.
5. **Append:** The event is appended to the NDJSON event log.
6. **Verification:** Verifiers check signatures, chain integrity, and Merkle root.

### 3.3 Trust Model

Provara's trust boundary is cryptographic:

```
  +--------------------------------------------------+
  |  VAULT (trusted -- signed by key holder)         |
  |  + Events + Keys + Manifest + Merkle Root +      |
  +--------------------------------------------------+
                    |
                    v
           External Verifier (untrusted)
```

Anything inside the vault is signed by the key holder. External verifiers can validate but not modify. The key holder is responsible for:

- Securing private keys (HSM, encrypted storage, offline backup).
- Maintaining backups (availability is not guaranteed by the protocol).
- Rotating keys if compromise is suspected.

---

## 4. Event Structure

Each event is a JSON object with the following fields:

**event_id (string, required):** Content-addressed identifier. Format: "evt_" followed by 32 lowercase hexadecimal characters. Derived as SHA-256 of canonical JSON bytes (excluding "event_id" and "signature" fields), truncated to 32 hex characters.

**type (string, required):** Event type name. Core types: GENESIS, OBSERVATION, ASSERTION, ATTESTATION, RETRACTION, KEY_REVOCATION, KEY_PROMOTION, REDUCER_EPOCH. Custom types MUST use reverse-domain notation (e.g., "com.example.audit.login").

**actor (string, required):** Human-readable actor identifier (e.g., "alice", "sensor_node_01").

**timestamp_utc (string, required):** ISO 8601 UTC timestamp (e.g., "2026-02-18T12:00:00Z").

**payload (object, required):** Event-specific data. Schema depends on event type.

**prev_event_hash (string, optional):** Event ID of the actor's immediately preceding event. Null for genesis events.

**signature (string, required):** Base64-encoded Ed25519 signature over canonical JSON bytes (excluding "signature" field).

**public_key (string, required):** Base64-encoded Ed25519 public key (32 bytes).

**key_id (string, required):** Key identifier. Format: "bp1_" followed by 16 lowercase hexadecimal characters. Derived as SHA-256 of raw public key bytes, truncated to 16 hex characters.

### 4.1 Example Event

```json
{
  "event_id": "evt_a1b2c3d4e5f6789012345678",
  "type": "OBSERVATION",
  "actor": "alice",
  "timestamp_utc": "2026-02-18T12:00:00Z",
  "payload": {
    "observation": "System initialized",
    "confidence": 0.95
  },
  "prev_event_hash": null,
  "signature": "MEUCIQDv...64-byte-Base64...AA==",
  "public_key": "MCowBQYDK2VwAyEAg...32-byte-Base64...==",
  "key_id": "bp1_27a6549d43046062"
}
```

---

## 5. Cryptographic Operations

### 5.1 Hashing

Implementations MUST use SHA-256 as specified in FIPS 180-4 [FIPS180-4].

- Output: 64 lowercase hexadecimal characters.
- Input: UTF-8 encoded bytes.
- Used for: event IDs, file integrity, Merkle nodes, state hash, key ID derivation.

### 5.2 Signing

Implementations MUST use Ed25519 as specified in RFC 8032 [RFC8032].

- Key size: 256-bit (32-byte public, 64-byte private with seed).
- Signatures: 64 bytes, Base64-encoded (standard alphabet with padding).
- Signing payload: SHA-256 of canonical JSON bytes (excluding "signature" field).

The "event_id" field MUST be included in the signing payload. The "signature" field MUST be excluded.

### 5.3 Canonical JSON

Implementations MUST use RFC 8785 (JSON Canonicalization Scheme) [RFC8785].

- Object keys MUST be sorted lexicographically by Unicode code point.
- No whitespace between tokens.
- No trailing commas.
- Numbers MUST NOT have leading zeros, positive signs, or trailing decimal zeros.
- Strings MUST use minimal escape sequences.
- Encoding MUST be UTF-8 without BOM.
- Null values MUST be preserved as "null" (MUST NOT be omitted).

Canonicalization ensures byte-identical serialization across implementations and platforms.

---

## 6. Causal Chain

Provara maintains per-actor causal chains via the prev_event_hash field.

### 6.1 Chain Model

Unlike blockchains that enforce global ordering, Provara maintains separate chains per actor:

```
Actor Alice:  evt_001 → evt_003 → evt_007 → evt_012
Actor Bob:    evt_002 → evt_004 → evt_009
Actor Carol:  evt_005 → evt_006 → evt_010 → evt_011
```

Benefits:

- **Concurrency:** Actors can append events independently without coordination.
- **Fork Detection:** Conflicting chains from the same actor are immediately detectable.
- **Efficiency:** Verification is O(n) per actor, not O(n²) across all actors.

### 6.2 Chain Rules

Implementations MUST follow these rules:

- First event by an actor: prev_event_hash MUST be null.
- Subsequent events: prev_event_hash MUST equal the event_id of that actor's immediately preceding event.
- Cross-actor references: prev_event_hash MUST NOT reference another actor's events.

### 6.3 Chain Validation Algorithm

To verify a chain:

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

---

## 7. Manifest and Integrity

### 7.1 Manifest Structure

The manifest provides integrity verification for all vault files:

```json
{
  "manifest_version": "1.0",
  "vault_uid": "my-vault",
  "generated_at": "2026-02-18T12:00:00Z",
  "files": [
    {"path": "events/events.ndjson", "sha256": "abc123...", "size": 1234},
    {"path": "identity/genesis.json", "sha256": "def456...", "size": 567},
    ...
  ],
  "merkle_root": "<SHA-256 Merkle root of file hashes>"
}
```

The manifest is signed with the vault's Ed25519 key.

### 7.2 Merkle Tree Construction

The Merkle tree is computed as follows:

1. Sort files lexicographically by path.
2. For each file, compute leaf_hash = SHA-256 of canonical JSON bytes of {"path": "...", "sha256": "...", "size": N}.
3. If leaf count is odd, duplicate the last leaf.
4. Compute internal nodes: node_hash = SHA-256(left_child_bytes || right_child_bytes).
5. The root is a single 64-character lowercase hex string.

The Merkle root is stored in merkle_root.txt for quick integrity checks.

### 7.3 Integrity Verification

To verify vault integrity:

1. Hash all files, compare against manifest entries.
2. Recompute Merkle root, compare against stored value.
3. Verify manifest signature.

Any mismatch indicates tampering or corruption.

---

## 8. Extension Mechanism

### 8.1 Custom Event Types

Implementations MAY define custom event types using reverse-domain notation:

- Format: com.example.domain.event_type
- Examples: com.acme.audit.login, org.hl7.fhir.observation
- Custom types MUST NOT collide with reserved core types.

Custom event types SHOULD be registered in the extension registry.

### 8.2 Extension Registry

The extension registry process allows proposing new event types without forking the core protocol:

1. Open a GitHub issue titled "RFC: event type <reverse-domain-name>".
2. Include: type name, owner/maintainer, payload schema (JSON Schema), reducer impact (none by default), security considerations.
3. Maintainers label as extension:proposed, extension:accepted, or extension:rejected.

Accepted extensions are listed in the extension registry document.

### 8.3 SCITT Compatibility

Provara implements IETF SCITT Phase 1 [SCITT] event types:

- **SIGNED_STATEMENT:** Maps to SCITT Signed Statements.
- **RECEIPT:** Captures transparency service receipts.

Export bundles are compatible with SCITT verifiers.

---

## 9. Security Considerations

### 9.1 Threat Model Summary

Provara is analyzed using the STRIDE framework [SHOSTACK]. Key findings:

- **Spoofing:** Mitigated by Ed25519 signatures. Residual risk: key theft via malware/phishing.
- **Tampering:** Mitigated by signatures + causal chains + Merkle trees. No known attacks.
- **Repudiation:** Mitigated by cryptographic binding. Signatures are non-repudiable.
- **Information Disclosure:** Out of scope (Provara does not encrypt).
- **Denial of Service:** User responsibility (backups, availability).
- **Elevation of Privilege:** No privilege model; cryptographic access control only.

### 9.2 Key Management Requirements

Private keys MUST be secured as follows:

- Store keys encrypted at rest (OS keychain, HSM, YubiKey).
- Never store private keys on the same drive as the vault.
- Maintain offline backups in separate physical locations.
- Use quorum keys for recovery (multi-location storage).
- Rotate keys immediately if compromise is suspected.

### 9.3 Replay, Forgery, and Tampering Resistance

Provara resists the following attacks:

- **Replay attacks:** Event IDs are content-addressed; duplicate events have identical IDs and are detected.
- **Forgery attacks:** Forging a signature requires breaking Ed25519 (128-bit security level).
- **Tampering attacks:** Modifying an event changes its event_id, breaking the causal chain and Merkle root.
- **Chain skipping:** Inserting events breaks prev_event_hash linkage.
- **Equivocation attacks:** SHA-256 collision resistance prevents two events with the same hash.

### 9.4 Post-Quantum Migration Path

Ed25519 and SHA-256 are vulnerable to large-scale quantum computers [SHOR]. Provara's migration path:

- **Dual-signing:** Support Ed25519 + ML-DSA (FIPS 204) signatures simultaneously.
- **Configurable hash functions:** Allow migration to SHA-3 or SHAKE.
- **Versioned event formats:** New profile versions can specify post-quantum algorithms.

A post-quantum extension is planned for 2027, contingent on NIST PQC standardization [NIST_PQC].

---

## 10. IANA Considerations

### 10.1 Event Type Namespace Registration

This document requests registration of the "Provara Event Type" namespace:

- **Namespace:** Provara Event Types
- **Registration policy:** First-come, first-served for reverse-domain names; expert review for core types.
- **Format:** Reverse-domain notation (e.g., com.example.event_type).
- **Reserved core types:** GENESIS, OBSERVATION, ASSERTION, ATTESTATION, RETRACTION, KEY_REVOCATION, KEY_PROMOTION, REDUCER_EPOCH, SIGNED_STATEMENT, RECEIPT.

### 10.2 Media Type Registration

This document requests registration of the following media type:

- **Type name:** application
- **Subtype name:** provara+json
- **Required parameters:** None
- **Optional parameters:** profile (e.g., "PROVARA-1.0_PROFILE_A")
- **Encoding considerations:** UTF-8; JSON per RFC 8785
- **Security considerations:** See Section 9 of this document
- **Interoperability considerations:** Provara implementations MUST use RFC 8785 canonical JSON
- **Published specification:** This document
- **Applications:** AI agent memory, supply chain provenance, legal discovery, audit logging
- **Fragment identifier considerations:** Event IDs (evt_...) may be used as fragment identifiers
- **Additional information:**
  - Magic number(s): None
  - File extension(s): .provara
  - Macintosh file type code(s): None
- **Person & email address to contact for further information:** contact@provara.dev
- **Intended usage:** COMMON
- **Restrictions on usage:** None
- **Author:** Hunt Information Systems LLC
- **Change controller:** IETF

---

## 11. References

### 11.1 Normative References

- [RFC2119] Bradner, S., "Key words for use in RFCs to Indicate Requirement Levels", BCP 14, RFC 2119, DOI 10.17487/RFC2119, March 1997.
- [RFC8174] Leiba, B., "Ambiguity of Uppercase vs Lowercase in RFC 2119 Key Words", BCP 14, RFC 8174, DOI 10.17487/RFC8174, May 2017.
- [RFC8032] Josefsson, S. and I. Liusvaara, "Edwards-Curve Digital Signature Algorithm (EdDSA)", RFC 8032, DOI 10.17487/RFC8032, January 2017.
- [RFC8785] Jones, M., "JSON Canonicalization Scheme (JCS)", RFC 8785, DOI 10.17487/RFC8785, June 2020.
- [FIPS180-4] NIST, "Secure Hash Standard (SHS)", FIPS PUB 180-4, DOI 10.6028/NIST.FIPS.180-4, 2015.
- [FIPS186-5] NIST, "Digital Identity Standard", FIPS PUB 186-5, DOI 10.6028/NIST.FIPS.186-5, 2023.

### 11.2 Informative References

- [RFC6962] Laurie, B., Langley, A., and E. Kasper, "Certificate Transparency", RFC 6962, DOI 10.17487/RFC6962, June 2013.
- [SCITT] IETF, "IETF SCITT Working Group Documents", https://datatracker.ietf.org/wg/scitt/documents/, 2025.
- [RFC3161] Adams, C., "Internet X.509 Public Key Infrastructure Time-Stamp Protocol (TSP)", RFC 3161, DOI 10.17487/RFC3161, August 2001.
- [SHOSTACK] Shostack, A., "Threat Modeling: Designing for Security", Wiley, 2014.
- [SHOR] Shor, P. W., "Polynomial-Time Algorithms for Prime Factorization and Discrete Logarithms on a Quantum Computer", SIAM Journal on Computing, Volume 26, Issue 5, Pages 1484-1509, 1997.
- [NIST_PQC] NIST, "Post-Quantum Cryptography Standardization", https://csrc.nist.gov/projects/post-quantum-cryptography, 2024.

---

## Appendix A: Event Schema (Normative)

The following JSON Schema defines the Provara event format:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": [
    "event_id", "type", "actor", "timestamp_utc",
    "payload", "signature", "public_key", "key_id"
  ],
  "properties": {
    "event_id": {
      "type": "string",
      "pattern": "^evt_[0-9a-f]{32}$"
    },
    "type": {
      "type": "string"
    },
    "actor": {
      "type": "string"
    },
    "timestamp_utc": {
      "type": "string",
      "format": "date-time"
    },
    "payload": {
      "type": "object"
    },
    "prev_event_hash": {
      "type": "string",
      "pattern": "^evt_[0-9a-f]{32}$"
    },
    "signature": {
      "type": "string"
    },
    "public_key": {
      "type": "string"
    },
    "key_id": {
      "type": "string",
      "pattern": "^bp1_[0-9a-f]{16}$"
    }
  }
}
```

---

## Appendix B: CLI Reference

The Provara CLI provides these commands:

```bash
# Create vault
provara init my-vault

# Append event
provara append my-vault \
  --type OBSERVATION \
  --data '{"key":"value"}' \
  --keyfile my-vault/identity/private_keys.json

# Verify integrity
provara verify my-vault

# Export for legal discovery
provara export my-vault \
  --format scitt-compat \
  --output evidence-bundle/

# List plugins
provara plugins list
```

---

## Acknowledgements

The authors thank the IETF SCITT working group for their work on supply chain integrity, which influenced Provara's design. The Provara protocol is available under Apache 2.0 at https://github.com/provara-protocol/provara.

---

## Author's Address

Hunt Information Systems LLC  
Email: contact@provara.dev  
URI: https://github.com/provara-protocol/provara
