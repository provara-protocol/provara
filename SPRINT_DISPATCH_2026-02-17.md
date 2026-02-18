# PROVARA SPRINT DISPATCH — 2026-02-17

**Sprint Goal:** Parallel execution across 5 strategic lanes with integration by EOD.

---

## SHARED CONTEXT — Copy Into Every Agent Session

```markdown
# PROVARA PROTOCOL — Agent Context Package

You are one of several AI agents working in parallel on the Provara Protocol.
You do NOT communicate with other agents. The owner coordinates. The repo is shared state.

## Identity
- **Public brand:** Provara (open-source protocol)
- **Parent entity:** Hunt Information Systems LLC (legal only, never in public content)
- **Protocol:** Provara Protocol v1.0 — Ed25519 + SHA-256 + RFC 8785 canonical JSON
- **License:** Apache 2.0
- **Repo:** https://github.com/provara-protocol/provara
- **Golden Rule:** "Truth is not merged. Evidence is merged. Truth is recomputed."

## Architecture (non-negotiable)
- Python 3.10+, single dependency: `cryptography >= 41.0`
- 7 core modules in `src/provara/`
- 312 tests (310 passed, 2 skipped) — pytest in `tests/`
- PROTOCOL_PROFILE.txt is FROZEN. Never modify. Code conforms to spec.
- Append-only event model. Deterministic reducer. Content-addressed event IDs.
- Vaults are UTF-8 JSON files designed for 50-year readability.

## Critical Rules
1. NEVER modify PROTOCOL_PROFILE.txt
2. NEVER commit private keys
3. NEVER introduce new dependencies without owner approval
4. ALWAYS run all tests before claiming done: `pytest`
5. NEVER weaken compliance tests — fix the code, not the test
6. NEVER output PII or the owner's real name
7. NEVER force push to main
8. Use "Provara" in all public content, "Hunt Information Systems LLC" only in legal docs

## Coordination Protocol
- AGENTS.md is the constitution
- TODO.md is the shared task board — read before starting, update when done
- Don't undo another agent's work unless tests fail or spec is violated
- Leave clear commit messages (Conventional Commits format)
- Leave the repo clean — passing tests, no uncommitted changes, updated TODO.md

## Your Output Contract
Every deliverable must include:
1. **What changed** — files created/modified
2. **Why** — which lane/task this addresses
3. **Test evidence** — proof it works (test output, verification commands)
4. **Handoff notes** — anything the next agent or owner needs to know
5. **TODO.md updates** — mark completed items, flag new discoveries
```

---

## AGENT 1: ARCHITECT

**Role:** Strategic orchestrator, spec integrity, documentation, cross-cutting design decisions

**Your lane this sprint:**

### Primary: Lane 5A — Interactive Playground Architecture
Design the browser-based WASM playground that lets developers create a vault, append events, verify chain, and visualize the hash chain — zero install. This is the #1 adoption accelerator.

Deliverables:
- `docs/PLAYGROUND_ARCHITECTURE.md` — System design doc covering: WASM compilation target (Rust→WASM), crypto primitives in browser (ed25519-compact vs dalek), UI framework choice, state management, what runs client-side vs nothing server-side
- `playground/` directory scaffold with package.json, build config, component stubs
- Sequence diagram: user creates vault → appends 3 events → verifies chain → sees visualization

### Secondary: Lane 5C — SCITT Compatibility Mapping
Write `docs/SCITT_MAPPING.md` — how Provara maps to the IETF SCITT architecture:
- Provara signed events ↔ SCITT Signed Statements
- Provara vault ↔ SCITT Transparency Service (file-first, not server-first)
- Provara checkpoints ↔ SCITT Receipts
- Gap analysis: COSE vs JSON+Ed25519, what a compatibility layer would need

### Tertiary: Review & Integrate
When other agents' outputs arrive, review for spec conformance and architectural coherence. Flag conflicts in TODO.md. Do not refactor unless tests break.

**Constraints:**
- You make design decisions, not implementation stubs full of `# TODO`
- Architecture docs must be specific enough that a Rust developer can build from them
- Reference PROTOCOL_PROFILE.txt for every cryptographic claim

---

## AGENT 2: RUSTACEAN

**Role:** Rust implementation, WASM compilation, crate publishing

**Your lane this sprint:**

### Primary: Lane 5B — `provara-rs` Foundation
Build the Rust implementation of Provara Protocol v1.0, conformant from spec alone.

Phase 1 deliverables (this sprint):
- `provara-rs/` workspace with two crates:
  - `jcs-rs` — standalone RFC 8785 canonical JSON crate (publishable to crates.io independently)
  - `provara-core` — Ed25519 signing, SHA-256 hashing, event creation, chain validation
- Pass the 7 test vectors from `test_vectors/vectors.json`
- Pass the canonical conformance suite from `test_vectors/canonical_conformance.json`
- `README.md` for each crate with usage examples

Crypto foundation:
- Use `ed25519-dalek` + `sha2` from RustCrypto for main implementation
- Use `serde_json` for JSON parsing, then apply JCS normalization
- `no_std` compatible where possible (enables future WASM + embedded targets)

### Secondary: WASM build target
- Add `wasm-pack` build config to `provara-core`
- Smoke test: compile to WASM, call `create_event()` and `verify_chain()` from JS
- Document binary size and any `no_std` constraints

**Constraints:**
- Build from PROTOCOL_PROFILE.txt, not from reading the Python source
- If the spec is ambiguous, document the ambiguity and make a decision (flag for Architect review)
- `jcs-rs` must be a standalone crate with zero Provara-specific assumptions
- Run `cargo clippy` and `cargo test` clean before claiming done

---

## AGENT 3: HARDENER

**Role:** Adversarial testing, formal verification, security hardening

**Your lane this sprint:**

### Primary: Lane 3A — TLA+ Model
Write a TLA+ specification for Provara's chain validation algorithm.

Deliverables:
- `formal/provara_chain.tla` — PlusCal specification modeling:
  - Hash chain integrity (every event's prev_hash links correctly)
  - Signature non-repudiation (every event signed by authorized key)
  - Temporal ordering (per-actor causal chains never go backwards)
  - Fork detection (divergent chains from same actor are detectable)
  - Key rotation (revocation + promotion is atomic, self-signing forbidden)
- `formal/provara_chain.cfg` — TLC model checker config
- `formal/README.md` — how to run the model checker, what properties it verifies
- Report of any invariant violations found (= spec holes)

### Secondary: Lane 3B — Forgery Test Suite
Expand adversarial testing:
- `tests/test_adversarial.py` with attack scenarios:
  - Event with valid signature but wrong chain position
  - Duplicate event_id injection
  - Key rotation self-signing attempt
  - Time-traveling timestamps
  - Corrupted checkpoint + valid events after it
  - Merkle tree with swapped leaf order
  - Event signed by revoked key
- Each test must assert the system correctly rejects the attack

### Tertiary: Lane 6A — Post-Quantum Readiness
Write `docs/POST_QUANTUM_MIGRATION.md`:
- Current state: Ed25519 (not quantum-safe)
- Target: ML-DSA (FIPS 204) or SLH-DSA (FIPS 205)
- Migration path: algorithm agility in signature field, dual-signing transition period
- Timeline: when to start, what triggers implementation
- Reference `integritychain/fips204` (Rust) and `GiacomoPope/dilithium-py` (Python)

**Constraints:**
- TLA+ spec must model the PROTOCOL_PROFILE.txt, not the Python implementation
- Forgery tests must each include a comment explaining the attack vector
- Don't implement post-quantum crypto — spec the migration path only

---

## AGENT 4: INTEGRATOR

**Role:** MCP server, CI/CD, packaging, developer experience

**Your lane this sprint:**

### Primary: Lane 4A — FastMCP Migration
Refactor `tools/mcp_server/server.py` to use the official `mcp.server.fastmcp.FastMCP` SDK.

Deliverables:
- Migrated MCP server using FastMCP patterns
- All existing MCP tools preserved with identical interfaces
- Structured output support (MCP spec revision 2025-06-18)
- Updated tests passing
- `docs/MCP_MIGRATION.md` — changelog and any breaking changes

### Secondary: Lane 4C — Docker Image
- `Dockerfile` — `docker run provara/server` gives MCP server + CLI + everything
- Multi-stage build: slim Python base, single dep installed, tests run in build stage
- `docker-compose.yml` for local development
- Document image size and startup time

### Tertiary: Lane 7A — RFC 3161 Timestamp Integration
Integrate `trailofbits/rfc3161-client` for trusted timestamps:
- `provara timestamp` CLI command that anchors current vault state hash to an external TSA
- Store timestamp response as a new event type: `TIMESTAMP_ANCHOR`
- Default TSA: FreeTSA.org. Support custom TSA via config.
- This is OPTIONAL — vaults work without it. Timestamps add legal admissibility.

**Constraints:**
- FastMCP migration must not break existing MCP clients
- Docker image must run on amd64 and arm64
- RFC 3161 integration must be optional — never a required dependency
- The `TIMESTAMP_ANCHOR` event type must use reverse-domain prefix per spec: `com.provara.timestamp_anchor`

---

## AGENT 5: WRITER

**Role:** Documentation, tutorials, content, developer experience prose

**Your lane this sprint:**

### Primary: Lane 5A — "Provara in 5 Minutes" Tutorial Series
Write 5 standalone tutorials, each under 5 minutes reading time:

1. **"Your First Vault"** — create, append 3 events, verify chain. CLI walkthrough.
2. **"Multi-Actor Dispute"** — two actors, conflicting observations, attestation resolution.
3. **"Checkpoint & Query"** — checkpoint a 1000-event vault, query by actor/date range.
4. **"MCP Integration"** — connect Provara vault to an AI agent via MCP server.
5. **"Anchor to L2"** — timestamp or anchor vault state to external trust anchor.

Deliverables:
- `docs/tutorials/01_first_vault.md` through `docs/tutorials/05_anchor.md`
- Each includes: prerequisite, complete CLI commands, expected output, "what just happened" explanation
- A `docs/tutorials/README.md` index

### Secondary: Lane 5A — Comparison Matrix
Write `docs/COMPARISON.md` — Provara vs Git vs Blockchain vs EventStore vs Sigstore:
- Use the competitive cheat sheet from the blueprint as the skeleton
- Expand each cell with 2-3 sentences
- Be honest about tradeoffs — developers respect this
- End with "When to use Provara" decision tree

### Tertiary: Blog Draft
Write `content/blog/why-your-ai-agents-memory-needs-cryptographic-proof.md`:
- Compare MCP Memory Server (knowledge graph, no integrity) vs Provara MCP Server
- Show the verifiability gap with a concrete scenario
- Target audience: developers building AI agents
- Tone: technical, not marketing. Evidence over hype.

**Constraints:**
- All public content uses "Provara" brand, "the Provara team," or "the maintainers"
- No first-person singular. Use "we" or passive voice.
- No PII, no location references, no owner identity signals
- Tutorials must use only commands that actually exist in the current CLI

---

## SYNC CHECK — Run After All Agents Complete

```bash
# 1. All tests pass
pytest

# 2. No PROTOCOL_PROFILE.txt modifications
git diff HEAD PROTOCOL_PROFILE.txt

# 3. No new dependencies added without approval
git diff HEAD requirements.txt pyproject.toml

# 4. No PII or OPSEC violations in any output
# (manual review)

# 5. TODO.md updated with completed items and new discoveries
cat TODO.md

# 6. No conflicting file modifications between agents
git status

# 7. All new files follow existing naming conventions
# (manual review)

# 8. Commit messages follow Conventional Commits format
git log -n 5
```

If conflicts exist between agent outputs:
1. Run tests — whichever version passes wins
2. Check PROTOCOL_PROFILE.txt — whichever conforms wins
3. If both pass and both conform — owner decides, other agent's work preserved as a branch

---

## SPRINT EXECUTION

**Owner:** Copy the SHARED CONTEXT block + one AGENT brief into each agent session.
**Launch all 5 agents in parallel.** They are designed to be non-blocking.
**Collect outputs** and run the SYNC CHECK before merging.

---

*"Truth is not merged. Evidence is merged. Truth is recomputed."*
