# Provara Offline-First Sync Protocol (v1.0)

## 1. Core Model

Provara synchronization is built on the principle that **"Truth is not merged. Evidence is merged. Truth is recomputed."**

Each actor maintains a local replica of the vault. While disconnected, actors may independently append events to their local per-actor causal chains. Upon reconnection, replicas synchronize by exchanging missing events.

### 1.1 Causal Determinism
Because each actor has their own causal chain (linked by `prev_event_hash`), most concurrent modifications are non-conflicting. An append by Actor A does not cryptographically interfere with an append by Actor B. 

### 1.2 Convergence
The goal of the sync protocol is to ensure that all replicas eventually possess the same set of events. Once the set of events is identical, the deterministic `SovereignReducer` ensures that the resulting state hash is byte-identical across all replicas.

---

## 2. Conflict Taxonomy

Conflicts in Provara are categorized based on their impact on chain integrity and semantic state.

### 2.1 Type 1: No Conflict (Parallel Appends)
- **Scenario**: Actor A appends `evt_A1` and Actor B appends `evt_B1` while disconnected.
- **Resolution**: Automatic. The union of events is taken. Since they belong to different causal chains, they are simply interleaved based on the total ordering rules.

### 2.2 Type 2: Ordering Ambiguity (Causal Forks)
- **Scenario**: Actor A appends `evt_A1` on Device 1 and `evt_A2` on Device 2, both referencing the same `prev_event_hash`.
- **Root Cause**: Usually indicates a private key compromise or a critical software bug allowing double-signing.
- **Resolution**: Flagged. A `com.provara.sync.conflict` event is generated. The reducer should move all beliefs from this actor into the `contested/` namespace from the fork point forward.

### 2.3 Type 3: Semantic Conflict (Referential Collision)
- **Scenario**: Two different actors independently attest to the same subject/predicate with different values.
- **Example**: Actor A attests `door:status = "open"`, Actor B attests `door:status = "closed"`.
- **Resolution**: Handled by the Reducer. Both values move to the `contested/` namespace until a resolution event (e.g., a higher-confidence ATTESTATION) is appended.

### 2.4 Type 4: Checkpoint Divergence
- **Scenario**: Two replicas create different signed checkpoints at different points in their local history.
- **Resolution**: Checkpoints are auxiliary optimizations. Replicas should keep the checkpoint with the highest `event_count` that they can verify.

---

## 3. Merge Algorithm

The merge algorithm must be **commutative** ($A \cup B = B \cup A$) and **associative** $((A \cup B) \cup C = A \cup (B \cup C))$.

### 3.1 Total Ordering Rules
To ensure all replicas recompute the same state, the partial order defined by causal chains must be extended to a deterministic total order:
1.  **Causal Dependency**: If $E_1$ is a causal ancestor of $E_2$ (via `prev_event_hash`), $E_1 < E_2$.
2.  **Logical Timestamp**: If no causal link exists, compare `ts_logical`.
3.  **Physical Timestamp**: If `ts_logical` is tied, compare `timestamp_utc`.
4.  **Content Hash**: If all above are tied, use the `event_id` (SHA-256) as the final tiebreaker.

### 3.2 Algorithm Pseudocode
```python
def merge_replicas(local_events, remote_events):
    # 1. Union set of events (deduplicate by event_id)
    all_events = set(local_events) | set(remote_events)
    
    # 2. Sort according to Total Ordering Rules
    sorted_events = sorted(all_events, key=total_order_key)
    
    # 3. Detect Forks
    forks = detect_causal_forks(sorted_events)
    if forks:
        for fork in forks:
            append_conflict_event(fork)
            
    return sorted_events
```

---

## 4. Conflict Resolution Events

When a Type 2 conflict (Fork) is detected, the synchronizing node SHOULD append a `com.provara.sync.conflict` event.

### 4.1 CONFLICT Event Schema
```json
{
  "type": "com.provara.sync.conflict",
  "actor": "sync_service",
  "payload": {
    "conflict_type": "CAUSAL_FORK",
    "actor_id": "bp1_compromised_actor",
    "fork_point_id": "evt_last_common_ancestor",
    "competing_event_ids": ["evt_fork_A", "evt_fork_B"]
  }
}
```

---

## 5. Wire Format (Delta Sync)

To minimize bandwidth, Provara uses a **Causal Delta** protocol.

### 5.1 Reconciliation
1.  **State Vector**: Each node maintains a map of `{actor_id: last_event_id}`.
2.  **Request**: Node A sends its State Vector to Node B.
3.  **Response**: Node B identifies all events in its log that are not causal ancestors of the IDs in A's State Vector and returns them as a Delta Bundle.

### 5.2 Efficiency
- **Bloom Filters**: For large vaults, nodes can exchange Bloom filters of `event_id` sets to identify missing events without full vector exchange.
- **Compression**: Delta bundles MUST be compressed using standard algorithms (e.g., Zstd) if the underlying transport does not provide compression.

---

## 6. Implementation Contract (sync_v1.py)

See `src/provara/sync_v1.py` for the proposed interface definitions.
