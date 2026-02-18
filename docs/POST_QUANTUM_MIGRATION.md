# Provara Post-Quantum Migration Strategy (Lane 6A)

## 1. Current State: Ed25519
Provara v1.0 relies on **Ed25519** (RFC 8032) for digital signatures and **SHA-256** for hashing. While SHA-256 is generally considered resistant to quantum attacks (requiring only larger output sizes to maintain security margins via Grover's algorithm), Ed25519 is based on the Elliptic Curve Discrete Logarithm Problem (ECDLP), which is vulnerable to Shor's algorithm.

## 2. Target Algorithms
To ensure 50-year longevity, Provara will migrate to NIST-standardized Post-Quantum Cryptography (PQC).

### Primary Target: ML-DSA (FIPS 204)
- **Formerly Dilithium**: Based on the hardness of the Module Learning with Errors (MLWE) problem.
- **Rationale**: Best balance of signature size and verification speed. Suitable for most Provara event signatures.
- **Reference**: `integritychain/fips204` (Rust), `GiacomoPope/dilithium-py` (Python).

### Secondary Target: SLH-DSA (FIPS 205)
- **Formerly SPHINCS+**: A stateless hash-based signature scheme.
- **Rationale**: Relies only on the security of the underlying hash function (SHA-256). Provides a "failsafe" if lattice-based assumptions (ML-DSA) are ever broken.
- **Use Case**: Long-term root keys and high-kinetic (L3) attestations.

## 3. Migration Path: Hybrid Signatures
Provara will employ a **Dual-Signature Transition Period** to maintain backward compatibility while providing quantum resistance.

### Phase 1: Algorithm Agility
- The `sig` field in the event schema will be extended to support algorithm identifiers (e.g., `sig: "alg:ed25519;data:..."`).
- The `keys.json` registry will support multiple public keys per actor.

### Phase 2: Hybrid Events
- Actors will sign events with BOTH Ed25519 and ML-DSA.
- Verifiers will accept events if at least one signature is valid (transitional) or require both (hardened).

### Phase 3: PQC-Only
- Legacy Ed25519 keys will be revoked via `KEY_REVOCATION`.
- New vaults will bootstrap with ML-DSA or SLH-DSA by default.

## 4. Implementation Triggers
- **Trigger 1**: Standardization of FIPS 204/205 (Complete).
- **Trigger 2**: Availability of production-grade, audited PQC libraries in Python/Rust (Active).
- **Trigger 3**: Emergence of "harvest now, decrypt later" threats for long-term archival data (Ongoing).

## 5. Timeline
- **Q3 2026**: Prototype ML-DSA support in `provara-rs`.
- **Q1 2027**: Introduce optional dual-signing in the Python reference implementation.
- **2030+**: Deprecate Ed25519 for new vaults.
