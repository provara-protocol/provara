# Provara Protocol v1.0 — Chain Validation Algorithm

> Status: Normative
> Profile: PROVARA-1.0_PROFILE_A
> Language: Implementation-agnostic pseudocode
>
> This document specifies the complete, step-numbered algorithm for validating
> a Provara event log. A conformant validator MUST perform every step in the
> order given. Two conformant validators MUST produce identical results for
> the same input.

---

## Prerequisites

Before running this algorithm, the implementation MUST have:

1. **SHA-256** — FIPS 180-4, output as 64 lowercase hex characters
2. **Ed25519** — RFC 8032 signature verification
3. **RFC 8785 Canonical JSON** — deterministic serialization (see `canonical_json.py`)
4. **Test vectors** — validate primitives against `test_vectors/vectors.json` before running this algorithm

---

## Input

```
INPUT:
  events          : ordered list of event objects (NDJSON, one per line)
  public_keys     : map of key_id → Ed25519PublicKey (loaded from vault)
  options         : {
      strict_mode   : boolean  // if false, unknown event types pass through
      actor_filter  : string?  // if set, only validate this actor's chain
  }

OUTPUT:
  result : {
      valid         : boolean
      errors        : list of { code: string, message: string, event_id: string? }
      event_count   : integer
      actors        : map of actor_id → { event_count, last_event_id, last_hash }
  }
```

---

## Algorithm

### Phase 0: Pre-flight

```
STEP 0.1 — Initialize state
  last_event_by_actor := {}   // actor_id → event_id (last seen)
  seen_event_ids      := {}   // set of event_id strings
  errors              := []
  valid               := true

STEP 0.2 — Validate event list is non-null
  IF events is null or not a list:
    APPEND error(PROVARA_E302, "events must be an ordered list", event_id=null)
    RETURN result(valid=false, ...)
```

### Phase 1: Per-Event Validation

For each event E at position i (0-indexed):

```
STEP 1.1 — Validate required fields
  FOR EACH required_field IN ["event_id", "type", "timestamp", "actor", "key_id", "sig"]:
    IF required_field NOT IN E:
      APPEND error(PROVARA_E300, "missing field: " + required_field, event_id=null)
      SET valid := false
      CONTINUE to next event  // skip remaining steps for this event

STEP 1.2 — Validate event_id format
  IF E.event_id does NOT match regex /^evt_[0-9a-f]{24}$/:
    APPEND error(PROVARA_E101, "event_id format violation", event_id=E.event_id)
    SET valid := false

STEP 1.3 — Validate key_id format
  IF E.key_id does NOT match regex /^bp1_[0-9a-f]{16}$/:
    APPEND error(PROVARA_E102, "key_id format violation", event_id=E.event_id)
    SET valid := false

STEP 1.4 — Validate timestamp format
  IF E.timestamp does NOT match ISO 8601 UTC (ending in "Z"):
    APPEND error(PROVARA_E105, "timestamp format violation", event_id=E.event_id)
    SET valid := false

STEP 1.5 — Validate event_id is content-addressed
  // Compute what the event_id should be:
  scratch := copy of E
  REMOVE scratch["event_id"]
  REMOVE scratch["sig"]
  canonical_bytes := RFC8785_canonical_bytes(scratch)
  expected_id := "evt_" + SHA256(canonical_bytes)[0:24]  // first 24 hex chars of 64-char hash

  IF E.event_id != expected_id:
    APPEND error(PROVARA_E004, "event_id does not match content hash", event_id=E.event_id)
    SET valid := false

STEP 1.6 — Check for duplicate event_id
  IF E.event_id IN seen_event_ids:
    APPEND error(PROVARA_E007, "duplicate event_id", event_id=E.event_id)
    SET valid := false
  ELSE:
    ADD E.event_id to seen_event_ids

STEP 1.7 — Validate Ed25519 signature
  // The signing payload is the event WITHOUT the "sig" field
  signing_scratch := copy of E
  REMOVE signing_scratch["sig"]
  signing_bytes := RFC8785_canonical_bytes(signing_scratch)

  pub_key := public_keys.get(E.key_id)
  IF pub_key is null:
    APPEND error(PROVARA_E204, "key_id not found in vault", event_id=E.event_id)
    SET valid := false
  ELSE:
    sig_bytes := BASE64_DECODE(E.sig)
    IF sig_bytes is null OR len(sig_bytes) != 64:
      APPEND error(PROVARA_E103, "signature format violation", event_id=E.event_id)
      SET valid := false
    ELSE IF NOT Ed25519_verify(pub_key, signing_bytes, sig_bytes):
      APPEND error(PROVARA_E003, "signature verification failed", event_id=E.event_id)
      SET valid := false

STEP 1.8 — Validate causal chain (prev_event_hash)
  prev := E.get("prev_event_hash")   // may be null

  IF prev is null:
    // First event from this actor in the log (or truly the first)
    // If we've seen a previous event from this actor, this is an error:
    IF E.actor IN last_event_by_actor:
      APPEND error(PROVARA_E002, "actor " + E.actor + " has null prev_event_hash but prior events exist", event_id=E.event_id)
      SET valid := false
  ELSE:
    // prev must reference this actor's immediately preceding event
    IF E.actor NOT IN last_event_by_actor:
      APPEND error(PROVARA_E013, "first event by actor has non-null prev_event_hash", event_id=E.event_id)
      SET valid := false
    ELSE IF last_event_by_actor[E.actor] != prev:
      APPEND error(PROVARA_E002, "prev_event_hash does not match actor's last event", event_id=E.event_id)
      SET valid := false

    // Cross-actor reference check: prev must belong to E.actor
    IF prev IN seen_event_ids:
      // Find the event with this id (requires index lookup or full scan)
      prev_event := lookup_by_id(events, prev)
      IF prev_event is not null AND prev_event.actor != E.actor:
        APPEND error(PROVARA_E005, "prev_event_hash references a different actor's event", event_id=E.event_id)
        SET valid := false
    ELSE IF prev is not null:
      // prev_event_hash references an event not yet seen
      APPEND error(PROVARA_E006, "prev_event_hash references unknown event_id", event_id=E.event_id)
      SET valid := false

  // Update the actor's last event pointer
  last_event_by_actor[E.actor] := E.event_id

STEP 1.9 — Validate event type format (if strict_mode)
  core_types := {"OBSERVATION", "ATTESTATION", "RETRACTION", "GENESIS",
                  "KEY_REVOCATION", "KEY_PROMOTION", "ASSERTION"}
  IF strict_mode AND E.type NOT IN core_types:
    // Custom types must use reverse-domain prefix
    IF E.type does NOT match /^[a-z0-9]+(\.[a-z0-9]+)+\.[a-z_]+$/:
      APPEND error(PROVARA_E301, "custom event type lacks reverse-domain prefix", event_id=E.event_id)
      SET valid := false
```

### Phase 2: Key Rotation Validation

After Phase 1, scan for KEY_REVOCATION / KEY_PROMOTION pairs:

```
STEP 2.1 — Collect rotation events
  revocations   := [E for E in events if E.type == "KEY_REVOCATION"]
  promotions    := [E for E in events if E.type == "KEY_PROMOTION"]

STEP 2.2 — Validate each KEY_REVOCATION
  FOR EACH rev IN revocations:
    IF "trust_boundary_event_id" NOT IN rev.get("payload", {}):
      APPEND error(PROVARA_E203, "KEY_REVOCATION missing trust_boundary_event_id", event_id=rev.event_id)
      SET valid := false

STEP 2.3 — Validate each KEY_PROMOTION
  FOR EACH promo IN promotions:
    promoted_key_id := promo.payload.get("promoted_key_id")

    // Self-signing check: the promoted key must NOT be the signer
    IF promo.key_id == promoted_key_id:
      APPEND error(PROVARA_E200, "KEY_PROMOTION signed by the key being promoted", event_id=promo.event_id)
      SET valid := false

    // Sequence check: there must be a KEY_REVOCATION for the same actor before this promotion
    has_preceding_revocation := any(
      r for r in revocations
      if r.actor == promo.actor
      AND r.timestamp < promo.timestamp
    )
    IF NOT has_preceding_revocation:
      APPEND error(PROVARA_E201, "KEY_PROMOTION without preceding KEY_REVOCATION", event_id=promo.event_id)
      SET valid := false
```

### Phase 3: State Hash Verification (Optional)

If a stored `state_hash` is provided for comparison:

```
STEP 3.1 — Run the reducer over all events
  state := reduce(events)   // per reducer_v0.py semantics

STEP 3.2 — Extract state_hash
  computed_hash := state["metadata"]["state_hash"]
  // state_hash is SHA-256 of canonical_bytes(state_without_metadata)

STEP 3.3 — Compare
  IF stored_state_hash is provided AND computed_hash != stored_state_hash:
    APPEND error(PROVARA_E009, "state_hash divergence", event_id=null)
    SET valid := false
```

### Phase 4: Result

```
STEP 4.1 — Assemble result
  RETURN {
    valid        : valid,
    errors       : errors,
    event_count  : len(events),
    actors       : { actor: { last_event_id, event_count }
                     for actor in last_event_by_actor }
  }
```

---

## Correctness Requirements

A conformant implementation MUST satisfy:

| Property | Requirement |
|----------|-------------|
| Determinism | Same input always produces identical valid/invalid result |
| Completeness | Every MUST rule in the spec generates at least one error code |
| Atomicity | Validation of one event MUST NOT affect another event's validity (no side effects across events) |
| Forward compatibility | Unknown event types in non-strict mode MUST NOT generate errors |
| Error codes | MUST use codes from `errors.json` when errors are returned |

---

## Reference Implementation

The Python reference implementation is in `SNP_Core/bin/backpack_integrity.py`.

Cross-validation: run the compliance tests against your output:
```bash
cd SNP_Core/test && PYTHONPATH=../bin python backpack_compliance_v1.py \
  ../examples/reference_backpack -v
```

All 17 tests MUST pass. If any fail, check your canonical JSON implementation
first — it is the most common source of divergence.

---

## Complexity

| Phase | Complexity | Notes |
|-------|-----------|-------|
| Phase 1 | O(n) | One pass over events, O(1) per event |
| Phase 2 | O(k) | k = number of rotation events, k << n |
| Phase 3 | O(n) | Reducer is O(n) in event count |
| Total | O(n) | Linear in vault size |

Large vaults (100K+ events) SHOULD use checkpoints to avoid re-reading from genesis.
See `SNP_Core/bin/checkpoint_v0.py` for the checkpoint protocol.

---

*Provara Protocol v1.0 | Apache 2.0 | provara.dev/spec/v1.0*
