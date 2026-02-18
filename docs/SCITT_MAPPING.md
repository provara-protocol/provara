# Provara SCITT Compatibility Mapping (Lane 5C)

This document maps the **Provara Protocol v1.0** to the IETF **Supply Chain Integrity, Transparency, and Trust (SCITT)** architecture. 

## 1. Architectural Alignment

Provara and SCITT share a common goal: providing a verifiable, tamper-evident record of assertions made by identified actors.

| SCITT Concept | Provara Concept | Mapping Notes |
|---------------|----------------|---------------|
| **Issuer** | **Actor** | An entity identified by an Ed25519 key (Key ID: `bp1_...`). |
| **Signed Statement** | **Signed Event** | A Provara event signed with Ed25519 over canonical JSON. |
| **Transparency Service** | **Vault (Backpack)** | A Provara vault acts as a file-first transparency service. |
| **Registry** | **Event Log** | The `events.ndjson` file is the append-only registry. |
| **Receipt** | **Checkpoint** | A signed state snapshot proves an event's inclusion in the chain. |
| **Artifact** | **Payload** | The data being asserted (e.g., identity, observation). |

## 2. Technical Mapping

### 2.1 Statement Format
- **SCITT**: Typically uses COSE (CBOR Object Signing and Encryption).
- **Provara**: Uses **RFC 8785 Canonical JSON** + **Ed25519**.
- **Bridge**: A Provara event can be wrapped in a COSE Sign1 structure for native SCITT consumption.

### 2.2 Identification
- **SCITT**: Uses DIDs (Decentralized Identifiers) or X.509 certificates.
- **Provara**: Uses **Self-Sovereign Key IDs** (`bp1_<hash>`).
- **Bridge**: Provara Key IDs can be represented as `did:provara:<key_id>`.

### 2.3 Inclusion Proofs
- **SCITT**: Uses Merkle Tree Inclusion Proofs.
- **Provara**: Uses **Causal Chain Hashing** (Linear) and **Manifest Merkle Trees** (Files).
- **Hardening**: To meet SCITT "Receipt" requirements, a Provara Checkpoint serves as proof that all events up to `event_count` are cryptographically sealed.

## 3. Gap Analysis

| Feature | SCITT Requirement | Provara v1.0 State |
|---------|-------------------|-------------------|
| **Serialization** | COSE/CBOR preferred | JSON/JCS (Standardized) |
| **Registration** | Synchronous ack | Asynchronous/Offline-first |
| **Transparency** | Publicly auditable | Private-by-default, auditable-by-invite |
| **Algorithm Agility** | Required | Supported (see Post-Quantum Roadmap) |

## 4. Compatibility Roadmap

To achieve full SCITT conformance, Provara will:
1.  **Export to COSE**: Add a tool to export Provara events as SCITT-compliant Signed Statements.
2.  **DID Method**: Register the `did:provara` method to provide standard-compliant actor identification.
3.  **Receipt Generation**: Extend `checkpoint_v0.py` to generate standard SCITT receipts.

## 5. Conclusion
Provara is architecturally a "SCITT-lite" implementation optimized for multi-agent memory and long-term durability. By using RFC 8785 and Ed25519, Provara provides the same cryptographic guarantees as SCITT while maintaining lower complexity for browser and AI agent integrations.
