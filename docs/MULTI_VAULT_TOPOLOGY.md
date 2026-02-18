# Multi-Vault Topology Patterns

Provara vaults can be organized into various network topologies depending on the trust requirements and operational scale of the deployment.

---

## 1. Hub-and-Spoke
A central authority vault acts as the primary aggregator for multiple peripheral actor vaults.

- **Use Case**: Enterprise audit logs, SaaS platforms, fleet management.
- **Sync Mechanism**: Peripherals push their local chains to the hub. The hub merges all spokes into a master event log.
- **Trust Model**: The Hub is a trusted aggregator but spokes maintain their own cryptographic identities. The Hub cannot forge spoke events but can withhold them.
- **Failure Mode**: Hub downtime prevents global synchronization, but spoke actors can continue recording observations locally. Hub compromise allows deletion of historical evidence from the master log.

## 2. Mesh (Peer-to-Peer)
All actors maintain their own replicas and sync directly with any other available peer.

- **Use Case**: Collaborative investigation, decentralized autonomous organizations (DAOs), multi-party dispute resolution.
- **Sync Mechanism**: Gossip protocol or periodic pairwise union-merges. Replicas eventually converge to the same event set.
- **Trust Model**: No central authority. Trust is derived entirely from the Ed25519 signatures and the causal chain integrity of each actor.
- **Failure Mode**: Network partitions result in delayed convergence (delayed "Truth"). Persistent partitions create long-lived contested beliefs.

## 3. Hierarchical
Vaults are nested according to organizational or logical structure (Org → Team → Individual).

- **Use Case**: Corporate compliance, government record-keeping, supply chain pedigree.
- **Sync Mechanism**: Roll-up. Child vaults are periodically summarized or fully merged into parent vaults. Higher levels may issue `ATTESTATION` events over child state hashes.
- **Trust Model**: Recursive attestation. Each level is responsible for the integrity of its children.
- **Failure Mode**: Compromise of a mid-level key affects its specific subtree only. Root keys provide the ultimate anchor for the entire hierarchy.

## 4. Federated
Multiple independent organizations sync relevant sub-chains across trust boundaries.

- **Use Case**: Inter-company audits, international logistics, joint research ventures.
- **Sync Mechanism**: Selective sync. Replicas only exchange events belonging to specific actors or namespaces defined in a federation contract.
- **Trust Model**: Shared responsibility. Each organization manages its own keys. Cross-org attestation events establish trust links between different sovereign domains.
- **Failure Mode**: Trust boundary breach (e.g., an org leaking its private key) requires a formal revocation ceremony across the entire federation.

---

## Summary Tradeoffs

| Pattern | Complexity | Scalability | Resilience | Trust Centricity |
|---------|------------|-------------|------------|------------------|
| Hub-and-Spoke | Low | Medium | Low | Centralized |
| Mesh | High | High | High | Distributed |
| Hierarchical | Medium | High | Medium | Delegated |
| Federated | High | Medium | High | Mutual |
