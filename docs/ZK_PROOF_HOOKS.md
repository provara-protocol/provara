# Provara ZK-State Proof Hooks (Lane 6A)

## 1. Objective
Enable Provara state hashes to be used as verifiable on-chain claims without revealing the entire event log. This allows for privacy-preserving audits and trustless integration with L1/L2 smart contracts.

## 2. Theoretical Path: Snapshot to ZK-Proof

The core idea is to generate a Zero-Knowledge Succinct Non-Interactive Argument of Knowledge (ZK-SNARK) that proves the following statement:

> "I know a signed event log that, when processed by the Provara Sovereign Reducer, results in State Hash H."

### 2.1 Recursive State Proofs
Since Provara event logs can be long, we will use recursive proof composition (e.g., via Halo2 or Plonky2) to prove the chain transition:
- `Proof(N)` proves `State(N-1) + Event(N) -> State(N)`
- `Proof(Genesis)` proves `InitialState + GenesisEvent -> State(0)`

### 2.2 Circuit Architecture
The ZK circuit will implement:
1.  **Ed25519 Signature Verification**: Proves the event was signed by an authorized key.
2.  **SHA-256 Hashing**: Proves the causal link to the previous event hash.
3.  **Reducer Logic (Subset)**: A constrained version of the `SovereignReducerV0` logic to prove belief promotion/retraction.

## 3. Integration Hooks

Provara will provide "hooks" to export data in formats suitable for ZK proof generation:

### 3.1 `provara zk-witness <vault>`
A CLI command to generate a "witness" file (JSON or binary) containing:
- The current state.
- The event sequence.
- Intermediate state transitions.
- Cryptographic signatures.

### 3.2 Smart Contract Anchors
A Solidity or Move contract that:
- Stores the latest `state_hash`.
- Provides a `verifyProof(bytes proof, bytes32 newStateHash)` function.
- Enables "Attestation as a Service" where on-chain actions are triggered by verified Provara beliefs.

## 4. Technology Stack
- **Languages**: Rust (core logic), Circom/Noir (circuit definition).
- **Provers**: SnarkJS (Groth16), Halo2.
- **Target Chains**: Solana, Ethereum (L2s like Arbitrum/Optimism).

## 5. Roadmap
- **Phase 1**: Prototype a SHA-256 chain verification circuit in Noir.
- **Phase 2**: Implement a simplified "Canonical Promotion" circuit.
- **Phase 3**: Full integration with `provara-rs` for browser-side proof generation.
