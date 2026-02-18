# Provara Interactive Playground — Architecture & Design

**Status:** Design Phase · **Date:** 2026-02-18 · **Target:** Lane 5A Adoption Accelerator

---

## Executive Summary

The Provara Interactive Playground is a **browser-based, zero-install environment** where developers can:
1. Create a cryptographic vault in seconds
2. Append events (observations, attestations) 
3. Verify the hash chain in real-time
4. Visualize the chain, signatures, and merkle tree
5. Export the vault as a valid `.provara` file

**Design Principle:** Make the first experience with Provara take <5 minutes, no CLI required, no installation. A dev who can try it in a browser is infinitely more likely to adopt.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Browser (Client-Side)                        │
│                                                                 │
│  ┌─────────────────┐         ┌──────────────────────────────┐  │
│  │   React UI      │         │   WASM Module               │  │
│  │  (Hooks)        │◄───────►│  provara-core (compiled)    │  │
│  │                 │         │  • SHA-256 hashing          │  │
│  │ • Vault Manager │         │  • Ed25519 signing          │  │
│  │ • Event Editor  │         │  • RFC 8785 canonicalization│  │
│  │ • Chain View    │         │  • Event creation           │  │
│  │ • Merkle Tree   │         │  • Chain validation         │  │
│  │   Visualizer    │         └──────────────────────────────┘  │
│  │                 │                                            │
│  │ • Export/Download│                                           │
│  └─────────────────┘         ┌──────────────────────────────┐  │
│         │                     │   IndexedDB (Ephemeral)     │  │
│         │                     │   • Current vault state     │  │
│         │                     │   • Event history           │  │
│         └────────────────────►│   • Session cache           │  │
│                               └──────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         │
         │ JSON export
         ▼
    User's Computer (Download)
    • vault.provara (NDJSON)
    • manifest.json
    • Key pair (if generated in browser)
```

**Key Architectural Decision:** Everything runs in the browser. Zero server-side state. Entire vault, including private keys, is stored locally in IndexedDB or downloaded by the user.

---

## Technology Stack

### Frontend

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Framework** | React 18+ | Declarative UI, hooks for state mgmt, large ecosystem |
| **Build Tool** | Vite | Fast HMR, minimal config, excellent WASM integration |
| **Styling** | Tailwind CSS | Rapid prototyping, responsive design, dark mode support |
| **State** | Zustand or Context API | Lightweight, React-native, no additional deps for MVP |
| **Visualization** | D3.js or Cytoscape.js | Hash chain DAG + merkle tree visualization |
| **UI Components** | shadcn/ui or Headless UI | Accessible, styled, composable (optional; can use Tailwind + custom) |

### Cryptography Layer (WASM)

**Source:** Rust implementation (`provara-rs/provara-core`) compiled to WebAssembly

| Component | Crate | Rationale |
|-----------|-------|-----------|
| **SHA-256** | `sha2` (RustCrypto) | Audited, FIPS 180-4 compliant, no_std compatible |
| **Ed25519** | `ed25519-dalek` or `ed25519` | Well-maintained, RFC 8032 conformant, WASM-friendly |
| **Canonical JSON** | `jcs-rs` (custom, standalone) | RFC 8785 conformance, minimal bloat, portable |
| **Serialization** | `serde_json` | De facto JSON standard in Rust + WASM |
| **Random** | `getrandom` via web-sys | CSPRNG via browser `crypto.getRandomValues()` |

**Build Target:** `wasm-pack build --target web`

**Binary Size Target:** <500KB (gzipped). Actual expected: ~200-300KB with tree-shaking.

### Storage

| Tier | Technology | Purpose |
|------|-----------|---------|
| **Ephemeral (Session)** | IndexedDB | Current vault, events, working state during session |
| **Download** | NDJSON + ZIP | Portable vault archive (manifest + events + optionally keys) |
| **Demo Vaults** | Static JSON | Pre-built examples (tutorial, demo attack scenario) |

---

## User Workflows

### Workflow 1: Create First Vault (5 min)

```
User opens playground.provara.dev
  ↓
Sees: "Create Your First Vault" → button
  ↓
Clicks → generates keypair in browser (via WASM)
  ↓
Displays: public key, key ID, import/export options
  ↓
User appends 3 events:
  - GENESIS event (auto-created)
  - OBSERVATION: "tested build pipeline"
  - ATTESTATION: "build passed"
  ↓
View chain visualization → see hash→hash→hash
  ↓
Click "Verify Chain" → ✓ All hashes valid, all sigs valid
  ↓
Download vault → vault.provara file (NDJSON)
  ↓
Copy vault to local machine, run: provara verify vault.provara
```

### Workflow 2: Multi-Actor Dispute (10 min)

```
Two actors, competing observations:
  - Alice: "code review passed"
  - Bob: "code review failed"
  ↓
Both sign their observation with their key
  ↓
Playground shows both in "contested" namespace
  ↓
User can inspect: who signed, when, what was their key
  ↓
User resolves: append ATTESTATION event with tie-breaker
  ↓
Chain now shows full dispute history + resolution
```

### Workflow 3: Learn Cryptography (Interactive)

```
User hovers over hash → see tooltip:
  "SHA-256 of this event's canonical JSON"
  [Show the canonical bytes] → [Computed hash]
  ↓
User hovers over signature → see:
  "Ed25519 signature by this key over the event"
  [Verify badge]
  ↓
User can manually corrupt an event and watch verification fail
  → "Bad signature detected! This would be rejected by the chain verifier."
```

---

## Component Architecture

### React Component Tree

```
<PlaygroundApp>
  ├── <Header>
  │   ├── Logo + Brand
  │   ├── Quick Help
  │   └── Settings (Dark Mode, Export Format)
  │
  ├── <MainLayout>
  │   ├── <LeftSidebar>
  │   │   ├── <VaultSelector>
  │   │   ├── <KeyManager>
  │   │   │   ├── Import existing key
  │   │   │   ├── Generate new key
  │   │   │   └── Display public key + key ID
  │   │   └── <Actions>
  │   │       ├── New Event
  │   │       ├── Import Vault
  │   │       ├── Export Vault
  │   │       └── Verify Chain
  │   │
  │   ├── <CentralCanvas>
  │   │   ├── <EventList>
  │   │   │   └── Each event shows:
  │   │   │       - event_id (truncated)
  │   │   │       - actor, timestamp
  │   │   │       - event_type badge (OBSERVATION, ATTESTATION, etc.)
  │   │   │       - namespace (canonical, local, contested, archived)
  │   │   │       - Expand to see full JSON
  │   │   │
  │   │   ├── <ChainVisualization>
  │   │   │   └── D3 DAG showing:
  │   │   │       - Nodes = events
  │   │   │       - Edges = prev_hash linkage
  │   │   │       - Color by namespace
  │   │   │       - Mouseover → highlight path
  │   │   │
  │   │   └── <EventEditor>
  │   │       ├── Event type selector
  │   │       ├── Fields form (actor, content, etc.)
  │   │       ├── Sign button (uses WASM)
  │   │       └── Preview (shows canonical JSON before append)
  │   │
  │   └── <RightSidebar>
  │       ├── <VerificationReport>
  │       │   └── Real-time check:
  │       │       - Chain integrity: ✓
  │       │       - All signatures valid: ✓
  │       │       - No tamper detected: ✓
  │       │
  │       ├── <MerkleTreeView>
  │       │   └── Tree visualization + root hash
  │       │
  │       └── <StateSnapshot>
  │           └── Current state_hash + namespaces
  │
  └── <Modal>: Import/Export, Key Management, Tutorial
```

### State Management (Zustand Store)

```typescript
// Single source of truth
interface PlaygroundStore {
  // Vault state
  vault: {
    events: Event[];
    manifest: Manifest;
    state_hash: string;
    merkle_root: string;
  };
  
  // Keys
  keys: {
    current_key_id: string;
    keys: Map<string, { public: string; private?: string }>;
  };
  
  // UI state
  ui: {
    selected_event_id: string | null;
    view_mode: 'list' | 'graph' | 'merkle';
    sidebar_open: boolean;
  };
  
  // Actions
  actions: {
    appendEvent: (event: Event) => Promise<void>;
    verifyChain: () => VerificationResult;
    generateKey: () => Promise<KeyPair>;
    importVault: (ndjson: string) => Promise<void>;
    exportVault: () => string;
  };
}
```

---

## WASM Integration Strategy

### Build Pipeline

```bash
# In provara-rs/provara-core/
wasm-pack build --target web --release

# Output:
# pkg/
#   ├── provara_core.js       (JS bindings)
#   ├── provara_core.d.ts     (TypeScript types)
#   └── provara_core_bg.wasm  (Binary)
```

### Exposed Functions (WASM Boundary)

```rust
// All functions defined in provara-core/src/lib.rs with #[wasm_bindgen]

#[wasm_bindgen]
pub fn create_event(
    event_type: &str,
    actor: &str,
    content: &str,
    prev_event_hash: Option<String>,
    // ... other fields
) -> Result<String, JsValue>; // Returns JSON-serialized event

#[wasm_bindgen]
pub fn compute_event_id(event: &str) -> String;

#[wasm_bindgen]
pub fn sign_event(event: &str, private_key: &str) -> Result<String, JsValue>;

#[wasm_bindgen]
pub fn verify_event(event: &str, public_key: &str) -> bool;

#[wasm_bindgen]
pub fn verify_chain(events_json: &str) -> VerificationResult;

#[wasm_bindgen]
pub fn canonical_json(obj: &str) -> String; // For display/learning

#[wasm_bindgen]
pub fn reduce(events: &str) -> ReducerOutput;

#[wasm_bindgen]
pub fn compute_merkle_root(files: &str) -> String;
```

### JS/WASM Interop

```javascript
// React component
import * as Provara from '../wasm/provara_core.js';

const signEvent = async (event, privateKey) => {
  try {
    const signed = Provara.sign_event(
      JSON.stringify(event),
      privateKey
    );
    return JSON.parse(signed);
  } catch (e) {
    console.error('Signing failed:', e);
    throw new Error(`Crypto error: ${e.message}`);
  }
};
```

---

## Data Flow & Correctness

### Append Event Flow

```
User fills form → Click "Append Event"
  ↓
Frontend validates (non-crypto)
  ↓
Call WASM: create_event() → returns unsigned event JSON
  ↓
Verify event_id is correct (deterministic)
  ↓
Call WASM: sign_event(event, private_key)
  ↓
Append to in-memory vault.events
  ↓
Call WASM: reduce(events) → updates state_hash
  ↓
Call WASM: verify_chain(events) → real-time validation
  ↓
IndexedDB: persist vault
  ↓
UI: refresh event list, update visualization
```

### Verification Guarantees

- **Chain Integrity:** prev_hash links form unbroken chain per actor
- **Signature Validity:** Ed25519 verifies over canonical JSON bytes
- **Determinism:** Same events always produce same state_hash
- **Namespace Correctness:** Reducer produces canonical/local/contested/archived correctly

---

## Security & Trust Model

### What Runs in the Browser

✅ **Safe & Necessary:**
- All cryptography (WASM-based)
- Event creation & signing
- Chain verification
- Visualization & UI state

❌ **Never on Browser:**
- Server-side vault storage (unless explicit opt-in)
- Private key escrow
- Centralized authority

### Private Key Handling

1. **Generated locally** in WASM, never transmitted
2. **Stored in IndexedDB** for session persistence (not encrypted at rest — browser security model assumes local security)
3. **Optional export** to file with explicit warning: "This is your private key. Guard it. Store securely."
4. **Optional import** from file for multi-device workflows (user responsibility)

### GDPR & Data Privacy

- **Zero server-side data retention** — playground has no backend database
- **Analytics** (optional): Session ID only, no event content logged
- **Downloads** are user-controlled — no automatic cloud sync
- **Static hosting** possible (GitHub Pages, Netlify, Cloudflare Pages)

---

## Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Load playground | <2s | All assets cached, WASM cached in browser |
| Generate keypair | <100ms | WASM CSPRNG |
| Create event | <50ms | WASM hashing + signing |
| Verify chain (100 events) | <200ms | All hashing in WASM |
| Visualize chain (100 events) | <500ms | D3 layout + React render |
| Export vault | <100ms | JSON serialization |

---

## MVP vs. Future

### MVP (Weeks 1–2)

✅ **In Scope:**
- React app with Vite build
- Event creation form (OBSERVATION, ATTESTATION types only)
- Real-time chain verification
- Event list view + basic JSON inspector
- Export vault as NDJSON
- WASM integration for crypto

❌ **Out of Scope (Phase 2):**
- D3 visualization (basic text list first)
- Merkle tree viewer
- Multi-key management
- Import from file
- Conflict resolution UI
- Mobile responsiveness

### Phase 2 (Weeks 3–4)

- Interactive D3 chain graph
- Merkle tree visualization
- Key import/export UI
- Conflict detection & resolution helpers
- Tutorial mode with guided steps
- Dark mode

### Phase 3+ (Future)

- Share vaults via URL (backend optional)
- Collaborative editing (multi-tab sync)
- Time-travel debugging (replay to any event)
- Checkpoint system explorer
- AI agent integration demo

---

## Example Deployment

### Option A: Static Hosting (Recommended MVP)

```bash
# Build
npm run build

# Deploy to Cloudflare Pages, Netlify, or GitHub Pages
# Everything runs client-side — zero backend needed
npm run deploy
```

### Option B: With Optional Backend (Future)

```
playground.provara.dev (static frontend)
  ↓
api.provara.dev/share (optional vault sharing service)
  ↓
  │
  └─ Receives vault JSON
    └ Returns URL: playground.provara.dev/?vault_id=abc123
    └ Vault stored encrypted (user's email + consent required)
```

---

## Success Metrics

### Developer Adoption

- **Time to first working vault:** <5 minutes
- **Bounce rate:** <20% (users who leave without trying)
- **"Aha moment" completion:** >80% (created vault + verified chain)
- **Export-to-local:** >50% (downloaded vault.provara file)

### Technical

- **WASM Binary Size:** <500KB gzipped
- **First Contentful Paint:** <1s
- **Chain verification time (100 events):** <250ms
- **Error recovery:** <1% uncaught exceptions (all errors caught gracefully)

---

## Handoff to Rust Implementer

The Rust implementer (Lane 5B — RUSTACEAN) will:

1. Build `provara-rs/provara-core` conformant to PROTOCOL_PROFILE.txt
2. Expose WASM-bindgen functions matching the signatures in this doc
3. Provide test vectors proving conformance
4. Build and publish to npm as `@provara/core` or similar

The Frontend Implementer will:

1. Scaffold React app using this component architecture
2. Integrate WASM module once published
3. Implement UI/UX following the workflows above
4. Ship MVP to static host

---

## Appendix: Reference Implementations

### Canonical JSON in Browser

```javascript
// Verify that WASM jcs-rs produces same output as Python canonical_json.py
import { canonical_json } from '@provara/core';

const event = {
  actor: "alice",
  event_type: "OBSERVATION",
  content: "test",
  timestamp: "2026-02-18T08:00:00Z",
  prev_event_hash: null,
};

const canonicalBytes = canonical_json(JSON.stringify(event));
console.log(canonicalBytes); 
// Should match: echo $event | python -c "import sys; from src.provara.canonical_json import canonical_bytes; print(canonical_bytes(sys.stdin.read()))"
```

### Ed25519 Signing Verification

```javascript
// Test that WASM ed25519-dalek produces valid signatures
import { sign_event, verify_event } from '@provara/core';

const event = { /* ... */ };
const privateKey = "..."; // Base64 encoded
const publicKey = "...";  // Base64 encoded

const signedEvent = sign_event(JSON.stringify(event), privateKey);
const isValid = verify_event(signedEvent, publicKey);
console.assert(isValid, "Signature should verify");
```

---

**Next Steps:**

1. ✅ This document (architecture + design) — DELIVERED
2. → Rust implementer: Build `provara-core` WASM bindings
3. → Frontend implementer: Scaffold React app using this design
4. → Integration: Wire WASM + React
5. → Deploy to static host

---

*"Truth is not merged. Evidence is merged. Truth is recomputed."*
