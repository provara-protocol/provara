# Design Principles — Hunt Information Systems

> North star for every architecture decision, product choice, and line of code.
> Written 2026-02-15. Updated as the business evolves.

---

## I. Company Structure

### Provara is the engine. Hunt Information Systems is the car.

| Entity | Role | Revenue |
|--------|------|---------|
| **Provara** (provara.dev) | Open protocol. Spec, reference impl, compliance suite. Free forever. | None — credibility and ecosystem. |
| **Hunt Information Systems** (huntinformationsystems.com) | Product company. Tools, dashboards, hosted services built on Provara. | Products, subscriptions, enterprise licensing. |

The protocol is Apache 2.0. The products are not. This is the Red Hat model:
give away the engine, sell the car.

Consulting is available as a premium, limited offering — not the core business.
The founder's time is spent on product surface, not client calls.

---

## II. Core Doctrine

### 1. Deterministic over probabilistic

Same inputs produce same outputs. Always. On any machine. Forever.
If the system can't guarantee this, it doesn't ship.

This applies to:
- The reducer (event replay = identical state hash)
- The build system (reproducible packages)
- The test suite (no flaky tests, no "works on my machine")

### 2. Logged over implicit

Every decision is recorded. Every model output is attributable.
No "it felt right." No silent mutations. No mystery state.

- Events are append-only and content-addressed
- Every observation is signed with Ed25519
- Every causal chain is independently verifiable
- If it's not in the log, it didn't happen

### 3. Gated over autonomous

Destructive actions require explicit, signed authority.
The default is always the action that can be undone.

| Tier | Risk | Gate |
|------|------|------|
| L0 | Data-only, reversible | Local reducer |
| L1 | Low-kinetic | Reducer + policy |
| L2 | High-kinetic | Multi-sensor + signed policy |
| L3 | Critical / irreversible | Human approval or remote signature |

Safety constraints only tighten automatically. Loosening requires L3 clearance.

### 4. Verifiable over trusted

Every system produces cryptographic proof of its own integrity.
Clients audit independently, without our involvement or permission.

- Merkle trees seal vault state
- Ed25519 signatures prove authorship
- SHA-256 hashes detect any modification
- No phone-home, no telemetry, no accounts required

### 5. Durable over clever

Design for the scenario where we no longer exist.
Open protocols. Documented formats. Zero vendor lock-in.
Your data survives our company.

- JSON events readable with any text editor for 50+ years
- SHA-256 and Ed25519 are industry standards in every language
- No proprietary formats. No binary blobs. No cloud dependencies.

### 6. Evidence over conclusions

> Truth is not merged. Evidence is merged. Truth is recomputed.

When combining data from multiple sources, never merge conclusions.
Merge raw observations, then rerun the deterministic reducer to derive
fresh conclusions from all available evidence.

This eliminates merge conflicts at the belief layer entirely.

---

## III. The Co-Pilot Model

### What we're building

AI handles repetition. Humans handle judgment.

A well-designed agent can:
- Draft code
- Refactor
- Run tests
- Suggest architecture
- Execute inside a sandbox
- Ask for approval on risky operations

That's a co-pilot.

### What we're not building

An AI that fully controls systems without supervision is not a goal.
That's outsourcing executive function. If it can silently act with no
guardrails, that's chaos — not intelligence.

### The infrastructure test

In 3 years, when agents are 10x better, they should plug into:

1. **A task queue** — proposed actions with approval gates
2. **A memory layer** — Provara vaults with cryptographic continuity
3. **A permission map** — keys, roles, scopes, tiered authority
4. **A rollback system** — append-only events, recomputable state

That's leverage. Not fantasy. Infrastructure.

---

## IV. Product Strategy

### Three lanes, one protocol

| Lane | Buyer | Description | Timeline |
|------|-------|-------------|----------|
| **AI Agent Memory** | Developers, AI companies | MCP server + hosted vaults for agent persistence | Now — MCP server shipped |
| **Enterprise Audit** | Compliance, legal, regulated industries | Tamper-evident audit trails with cryptographic proof | Medium-term |
| **Family Vaults** | Individuals, families | Personal sovereign memory, inheritance, legacy | Long-term (provara.app) |

### Priority: Lane 1 first

The MCP server is shipped. The AI agent memory market is white-hot.
Nobody else has a cryptographically-signed, tamper-evident memory layer
for agents. We're in a category of one.

Lane 2 (enterprise) and Lane 3 (consumer) build on the same protocol
but require different product surfaces. Lane 1 validates the technology
and generates developer awareness.

### Competitive position

| Competitor | Approach | Our differentiator |
|------------|----------|-------------------|
| Recall Network | Blockchain-based AI memory (tokens, on-chain) | We're crypto-free, local-first. No chain dependency. |
| Axon Framework | Java event sourcing (enterprise) | We're AI-agent-native, not Java-enterprise. |
| IBM Sovereign Core | Enterprise sovereign AI infra | We're a protocol, not a platform. Open, not proprietary. |
| Vector DBs (Pinecone, etc.) | Embedding-based retrieval | We're event-sourced truth, not fuzzy similarity. |

The unique niche: **local-first, crypto-free, tamper-evident sovereign memory
for AI agents.** Nobody else occupies this exact space.

---

## V. Technical Principles

### Architecture

```
EVENTS (append-only) --> REDUCER (deterministic) --> BELIEFS (derived)
                                                         |
                                                    MANIFEST + MERKLE ROOT
                                                    + Ed25519 SIGNATURE
```

- Events are the source of truth. Everything else is derived.
- State is a cache. Delete it and replay from genesis — same result.
- Manifests seal the vault. Any modification breaks the Merkle root.

### Code standards

- **No new dependencies** without explicit approval. Single-dep design is intentional.
- **No over-engineering.** Three similar lines > premature abstraction.
- **Tests before claims.** Evidence before assertions. Always.
- **Match existing patterns.** Read before writing. Respect the codebase.

### Cryptographic stack (frozen)

| Function | Algorithm | Spec |
|----------|-----------|------|
| Hashing | SHA-256 | FIPS 180-4 |
| Signing | Ed25519 | RFC 8032 |
| Canonical JSON | JCS-subset | RFC 8785 |
| Key IDs | `bp1_` + SHA-256(pubkey)[:16 hex] | Provara v1 |

This stack is frozen in `PROTOCOL_PROFILE.txt`. It does not change.

---

## VI. Business Operations

### Owner's lane vs. AI's lane

| Owner handles | AI agents handle |
|---------------|------------------|
| Websites, dashboards, UI | Backend code, protocol implementation |
| Domains, DNS, deployment | Test coverage, edge cases |
| Business formation, legal | Documentation, CI/CD |
| Marketing, outreach | Code quality, refactoring |
| Product design, UX | Security audits, compliance |

The owner is a visual-first operator. AI agents are the backend army.
Maximum autonomy on backend work. Clean, tested, committable state
at the end of every session.

### Revenue model

- **Primary:** Products built on Provara (subscriptions, licensing)
- **Secondary:** Premium consulting (limited, 2-3 clients/quarter)
- **Never:** Selling the protocol itself, vendor lock-in, data monetization

### Brand architecture

| Brand | Domain | Purpose |
|-------|--------|---------|
| Hunt Information Systems | huntinformationsystems.com | Corporate identity, consulting, enterprise |
| Provara | provara.dev | Protocol documentation, developer community |
| Provara (consumer) | provara.app | Family vaults, personal memory (future) |

---

## VII. Operational Guardrails

### Calm, modular, reversible.

Every system we build follows these constraints:

1. **Calm** — No rush deployments. No panic fixes. Stability over speed.
2. **Modular** — Components can be replaced independently. No monoliths.
3. **Reversible** — Every action can be undone or replayed. No one-way doors without L3 approval.

### What "safe automation" means

- All destructive commands go through a queue. Nothing runs raw.
- Everything can be replayed or rejected.
- Every model output is attributable to a specific actor and key.
- Future-you should need permission to do certain things.

We're not preparing for an AI. We're preparing for automation to be safe.

### The honesty check

AI can support thinking. It cannot replace human grounding.
Keep real-world anchors strong. If a decision feels like it needs
a human gut check, it does.

---

## VIII. What We Don't Do

- **No blockchain.** Merkle trees + causal chains. Not Bitcoin.
- **No tokens.** No cryptocurrency. No speculative assets.
- **No NFTs.** Digital ownership through keys, not marketplaces.
- **No surveillance.** Memory belongs to the owner. Period.
- **No cloud dependency.** Works offline. No internet required after setup.
- **No vendor lock-in.** Open formats. Open protocols. Your data leaves with you.
- **No magic.** Cryptographic guarantees, not corporate promises.

---

*Sovereign Memory. Verifiable Continuity.*

*Hunt Information Systems LLC, 2026*
