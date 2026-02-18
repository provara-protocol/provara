# Playground Interaction Flow Diagrams

## Sequence 1: Create First Vault

```
User                    Browser (React)           WASM Module          IndexedDB
─────────────────────────────────────────────────────────────────────────────────

User opens playground
 │                       
 ├─────────────────────► Page Load
 │                       │
 │                       ├─────────► Load @provara/core WASM ◄────────┐
 │                       │           (from npm/CDN)                   │
 │                       │◄──────────────────────────────────────────┘
 │                       │
 │◄─────────────────────● Render UI
 │                       
User clicks "Generate Key"
 │                       
 ├─────────────────────► Click Handler
 │                       │
 │                       ├──────────► generate_keypair()
 │                       │            (CSPRNG: crypto.getRandomValues())
 │                       │◄──────────
 │                       │ (public_key, private_key, key_id)
 │                       │
 │                       ├──────────────────────────────────────────► Save Key
 │                       │                                            (IndexedDB)
 │                       │                                           ◄────────
 │                       │
 │◄─────────────────────● Show Key + Warning
 │                       "Store your private key securely"
 │
User appends 3 events
 │
 ├─────────────────────► New Event Form
 │                       │
 │                       ├──────────► create_event(
 │                       │               event_type="OBSERVATION",
 │                       │               actor="alice",
 │                       │               content="tested pipeline"
 │                       │            )
 │                       │◄───────────
 │                       │ (unsigned event JSON)
 │                       │
 │                       ├──────────► compute_event_id(event)
 │                       │            (SHA-256 of canonical JSON)
 │                       │◄───────────
 │                       │ (event_id = "evt_abc123...")
 │                       │
 │                       ├──────────► sign_event(event, private_key)
 │                       │            (Ed25519 signature over event)
 │                       │◄───────────
 │                       │ (sig = "base64_encoded...")
 │                       │
 │                       ├──────────────────────────────────────────► Append to Vault
 │                       │                                            (IndexedDB)
 │                       │                                           ◄────────
 │                       │
 │◄─────────────────────● Refresh Event List
 │                       (Event 1/3 appended)
 │
 [Repeat 2 more times for events 2 & 3]
 │
User clicks "Verify Chain"
 │
 ├─────────────────────► Verify Button
 │                       │
 │                       ├──────────► verify_chain(
 │                       │               events=[event1, event2, event3]
 │                       │            )
 │                       │
 │                       │ [WASM checks:]
 │                       │ • prev_hash linkage ✓
 │                       │ • All signatures valid ✓
 │                       │ • No tampering ✓
 │                       │
 │                       │◄───────────
 │                       │ (VerificationResult { valid: true, ... })
 │                       │
 │◄─────────────────────● Show "✓ Chain Valid"
 │                       (all badges green)
 │
User clicks "Download"
 │
 ├─────────────────────► Export Button
 │                       │
 │                       ├──────────────────────────────────────────► Read All Events
 │                       │                                            (IndexedDB)
 │                       │                                           ◄────────
 │                       │
 │                       ├──────────► reduce(events)
 │                       │            (compute final state_hash)
 │                       │◄───────────
 │                       │
 │                       ├──────────► compute_merkle_root()
 │                       │            (file tree hash)
 │                       │◄───────────
 │                       │
 │◄─────────────────────● Trigger Download
 │                       (vault.provara = NDJSON with manifest)
 │
User saves vault.provara locally
 │
 └─ Done! ✓
```

---

## Sequence 2: Append Event & Verify

```
Actor (alice)           Browser UI               WASM              Zustand Store
────────────────────────────────────────────────────────────────────────────────

Alice fills event form
 │
 ├──► Type: ATTESTATION
 ├──► Content: "code review passed"
 ├──► Sig: (empty, will be generated)
 │
Alice clicks "Sign & Append"
 │
 └─────────────────────► AppendEventForm Component
                        │
                        ├─ Validate fields (client-side)
                        │
                        ├──────────► create_event({
                        │               event_type: "ATTESTATION",
                        │               actor: "alice",
                        │               content: "code review passed",
                        │               timestamp: "2026-02-18T10:30:00Z",
                        │               prev_event_hash: "evt_prev123..." (last event from alice)
                        │            })
                        │◄───────────
                        │ event (unsigned)
                        │
                        ├──────────► compute_event_id(event)
                        │◄───────────
                        │ event_id = "evt_abc123..."
                        │
                        ├──────────► sign_event({...event}, private_key_alice)
                        │◄───────────
                        │ sig = "base64_...ed25519..."
                        │
                        ├──► Add sig field to event
                        │
                        ├─────────────────────────────────────────► appendEvent(event)
                        │                                           │
                        │                                           ├─ Add to vault.events
                        │                                           │
                        │                                           └─ Re-render
                        │◄─────────────────────────────────────────
                        │
                        ├──────────► verify_chain(vault.events)
                        │            (validate all 4 events now)
                        │◄───────────
                        │ VerificationResult { valid: true, ... }
                        │
                        ├─────────────────────────────────────────► setVerification(result)
                        │                                           │
                        │                                           └─ Update UI
                        │◄─────────────────────────────────────────
                        │
                        ◄─ Update RightSidebar: "✓ Chain Valid"
                        └─ Highlight new event in list
```

---

## Sequence 3: Multi-Actor Dispute Resolution

```
Alice                   Vault (Events)              Bob                 Verifier
────────────────────────────────────────────────────────────────────────────────

Alice appends:
 │
 └─► OBSERVATION: "build passed"
     (sig by alice, event_id: evt_obs_alice_1)
     │
     ▼ [Vault now has 1 event]


Bob appends:
 │
 └─► OBSERVATION: "build failed"
     (sig by bob, event_id: evt_obs_bob_1)
     (prev_event_hash: null — Bob is first actor, separate chain)
     │
     ▼ [Vault now has 2 events; reducer marks both as "contested"]


Verifier queries vault:
 │
 └─► Read events
     │
     ├─ Alice's chain: evt_obs_alice_1 (canonical namespace, if trusted)
     ├─ Bob's chain: evt_obs_bob_1 (contested namespace, conflicting)
     │
     └─► Display conflict in UI:
         ┌──────────────────┐
         │  CONFLICT        │
         │  ================│
         │  Alice: PASSED   │
         │  Bob: FAILED     │
         └──────────────────┘


Authority appends:
 │
 └─► ATTESTATION: "Bob is mistaken; logs show PASSED"
     (sig by authority, references both conflicting observations)
     │
     ▼ [Vault now has 3 events; reducer:
        • Moves Alice's obs → canonical
        • Moves Bob's obs → archived (resolved)
        • Authority's attestation → canonical (trusted)]


Verifier re-queries:
 │
 └─► Read events (all 3)
     │
     ├─ Alice's observation: canonical ✓
     ├─ Authority's attestation: canonical ✓ (resolves dispute)
     ├─ Bob's observation: archived (disproven)
     │
     └─► Display resolution in UI:
         ┌──────────────────────────────┐
         │  RESOLVED                    │
         │  ==========================  │
         │  Outcome: PASSED             │
         │  Authority: verified-alice   │
         │  Attestation: "Logs show..." │
         └──────────────────────────────┘
```

---

## Data Structure: Event → WASM → Verification

```
┌─────────────────────────────────────────────────────────┐
│ User Input (Form)                                       │
├─────────────────────────────────────────────────────────┤
│ event_type: "ATTESTATION"                               │
│ actor: "alice"                                          │
│ content: "code review passed"                           │
│ timestamp: "2026-02-18T10:30:00Z"                      │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ WASM: create_event()                                    │
├─────────────────────────────────────────────────────────┤
│ Input: { event_type, actor, content, timestamp, ... }  │
│ Output: unsigned event JSON                            │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ Unsigned Event                                          │
├─────────────────────────────────────────────────────────┤
│ {                                                       │
│   "actor": "alice",                                     │
│   "event_type": "ATTESTATION",                          │
│   "content": "code review passed",                      │
│   "timestamp": "2026-02-18T10:30:00Z",                 │
│   "prev_event_hash": "evt_xyz123..."                   │
│ }                                                       │
└────────────────┬────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
    ┌──────────────────┐  ┌──────────────────┐
    │ WASM:            │  │ WASM:            │
    │ compute_event_id │  │ sign_event       │
    └────────┬─────────┘  └────────┬─────────┘
             │                     │
             ▼                     ▼
    event_id =                sig =
    "evt_" +                  "base64_encode(
    SHA256(                     ed25519_sign(
      RFC8785(event)              SHA256(RFC8785(event))
    )[:24]                    )"
             │                     │
             └────────┬────────────┘
                      │
                      ▼
         ┌──────────────────────────────┐
         │ Signed Event (Ready to Append)
         ├──────────────────────────────┤
         │ {                            │
         │   "event_id": "evt_abc123...",
         │   "actor": "alice",          │
         │   "event_type": "ATTESTATION",
         │   "content": "...",          │
         │   "timestamp": "...",        │
         │   "prev_event_hash": "...",  │
         │   "sig": "base64_..."        │
         │ }                            │
         └────────────┬─────────────────┘
                      │
                      ▼
         ┌──────────────────────────────┐
         │ Append to vault.events       │
         │ (IndexedDB + Zustand store)  │
         └────────────┬─────────────────┘
                      │
                      ▼
         ┌──────────────────────────────┐
         │ WASM: verify_chain()         │
         │ Input: [all events]          │
         ├──────────────────────────────┤
         │ Checks:                      │
         │ ✓ prev_hash chain integrity  │
         │ ✓ Ed25519 sig valid          │
         │ ✓ event_id deterministic     │
         │ ✓ No tampering               │
         └────────────┬─────────────────┘
                      │
                      ▼
         ┌──────────────────────────────┐
         │ VerificationResult           │
         ├──────────────────────────────┤
         │ {                            │
         │   "valid": true,             │
         │   "chain_integrity": true,   │
         │   "all_sigs_valid": true,    │
         │   "errors": []               │
         │ }                            │
         └────────────┬─────────────────┘
                      │
                      ▼
         ┌──────────────────────────────┐
         │ UI: RightSidebar             │
         │ Displays "✓ Chain Valid"     │
         │ with all badges green        │
         └──────────────────────────────┘
```

---

## Export & Download Flow

```
User clicks "Download Vault"
 │
 └─ Browser computes:
    │
    ├─► reduce(events) → state_hash
    │
    ├─► compute_merkle_root(files) → merkle_root
    │
    └─► Generate NDJSON:
        
        line 1: {"manifest": {"version":"1.0","created_at":"...",
                              "state_hash":"...", "merkle_root":"..."}}
        line 2: {"event": event_1}
        line 3: {"event": event_2}
        ...
        line N: {"event": event_N}


 │
 └─ Browser creates Blob
    │
    └─ Trigger download:
       <a href="blob:..." download="vault.provara">


 │
 └─ User saves vault.provara

       User can now:
       - Email vault.provara to teammate
       - Push to Git repo
       - Run: provara verify vault.provara ✓
       - Import into another Provara instance
```

---

*"Truth is not merged. Evidence is merged. Truth is recomputed."*
