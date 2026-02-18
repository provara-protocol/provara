# Provara Formal Specification (TLA+)

This directory contains the formal specification of the Provara Protocol using TLA+.

## Contents

- `Provara.tla`: The core specification modeling the causal chain, Merkle roots, and vault sealing.
- `ProvaraMC.cfg`: TLC model checker configuration for verifying core invariants.
- `ProvaraFork.tla`: Models adversarial scenarios, specifically fork attacks, to prove they are detectable.
- `ProvaraPlusCal.tla`: A PlusCal version of the protocol, providing a higher-level algorithmic view.

## Model Summary

The specification models the following protocol components:
- **Events**: Content-addressed records chained per-actor.
- **Signatures**: Abstracted cryptographic signatures ensuring non-repudiation.
- **Merkle Root**: Global integrity anchor recomputed on each append.
- **Sealing**: The mechanism to transition a vault to a permanently read-only state.

## Verified Invariants

The following safety properties are verified by TLC:
1. **EventIdsUnique**: No two distinct events share the same `event_id`.
2. **ChainIntegrity**: Every event's `prev_event_hash` correctly points to the preceding event by the same actor.
3. **SignatureValidity**: Every event in the log is signed by the actor who produced it.
4. **NoForks**: No actor can produce divergent histories (forks) without detection.
5. **MerkleConsistency**: The Merkle root always accurately reflects the full sequence of events.
6. **SealFinality**: Once a vault is sealed, its event log remains immutable for all future states.

## Running the Model Checker

To verify the specification using the TLA+ Tools:

1. Ensure you have `tla2tools.jar` installed.
2. Run TLC on the core specification:
   ```bash
   java -cp tla2tools.jar tlc2.TLC Provara.tla -config ProvaraMC.cfg
   ```

## Limitations

- **Cryptographic Abstraction**: Hashes and signatures are modeled as abstract functions or simple mappings. The proof assumes the underlying cryptographic primitives (Ed25519, SHA-256) are collision-resistant and unforgable.
- **Finite Bounds**: The model is checked within finite bounds (e.g., `MaxEvents=5`, `MaxActors=3`) to ensure termination.
