# Provara Spec Decisions — Reconstructed from Profile + Code

This document identifies the 8 open spec decisions (originally from the lost blueprint) that have been reconstructed by analyzing `PROTOCOL_PROFILE.txt` and the reference Python implementation.

---

### 1. Tie-breaking for Identical Timestamps
**Ambiguity:** `PROTOCOL_PROFILE.txt` mandates reducer determinism but doesn't specify how to handle two events with identical `timestamp_utc`.  
**Current Resolution:** The sync layer (`sync_v0.py`) enforces a deterministic sort order using `(timestamp_utc, event_id)`. The reducer processes them in the resulting sequence.  
**Decision:** `(timestamp_utc, event_id)` is the normative tie-breaker for Profile A.

### 2. RETRACTION Event Schema
**Ambiguity:** `PROTOCOL_PROFILE.txt` lists `RETRACTION` as a core type but doesn't define its payload requirements.  
**Current Resolution:** `reducer_v0.py` requires `subject` and `predicate` in the payload. If the belief is canonical, it archives it with `retracted: true`.  
**Decision:** `RETRACTION` payload MUST contain `subject` and `predicate`. It MAY contain `reason`.

### 3. Namespace Promotion (Local to Canonical)
**Ambiguity:** READMEs suggest "auto-promotes on no conflict," but `reducer_v0.py` requires an explicit `ATTESTATION` event to move a belief from `local/` to `canonical/`.  
**Current Resolution:** No auto-promotion is currently implemented. Beliefs stay in `local/` until attested.  
**Decision:** Profile A requires explicit `ATTESTATION` for canonical status. `local/` is for unverified observations only.

### 4. Contested Resolution Mechanism
**Ambiguity:** How are contested beliefs resolved?  
**Current Resolution:** `reducer_v0.py` marks them as `AWAITING_RESOLUTION` and captures all evidence. Resolution is currently only possible by a subsequent `ATTESTATION` which clears the contested state for that key.  
**Decision:** Resolution of a contested key is achieved by an `ATTESTATION` or `RETRACTION` event for that same key.

### 5. Deleted Files in Merkle Tree
**Ambiguity:** How are file deletions reflected in the Merkle root?  
**Current Resolution:** `manifest_generator.py` only includes files currently present in the directory. The manifest itself is a snapshot.  
**Decision:** The Merkle root represents the *current* state of the backpack. Deletion is reflected by the absence of the file entry in the next signed manifest.

### 6. Key Promotion Authority (Quorum)
**Ambiguity:** `PROTOCOL_PROFILE.txt` says "surviving trusted authority" but doesn't define quorum.  
**Current Resolution:** `rekey_backpack.py` and `backpack_signing.py` allow any key with `root` role to promote a new key.  
**Decision:** In Profile A, a single `root`-privileged key is sufficient for `KEY_PROMOTION`. Future profiles may introduce M-of-N quorums.

### 7. Safety Tier Ratcheting (Loosening)
**Ambiguity:** How is a safety tier "loosened"?  
**Current Resolution:** Not fully implemented in the reducer, but `PROTOCOL_PROFILE.txt` mentions "explicit authority from a key with L3 clearance."  
**Decision:** Safety tiers are stored in `policies/safety_policy.json`. Loosening requires a `POLICY_UPDATE` event (or equivalent) signed by an L3-authorized key.

### 8. State Hash Scope (Metadata Exclusion)
**Ambiguity:** `PROTOCOL_PROFILE.txt` says to exclude the "metadata block," but `reducer_v0.py` includes a `metadata_partial` block (excluding only the `state_hash` itself).  
**Current Resolution:** The code includes `last_event_id`, `event_count`, `current_epoch`, and `reducer` info in the hash.  
**Decision:** The normative scope for Profile A `state_hash` includes all namespaces PLUS the partial metadata block as implemented in `reducer_v0.py`.
