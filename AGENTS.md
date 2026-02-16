# AGENTS.md — Universal Project Instructions for AI Coding Agents

> **This file is the single source of truth for any AI agent working on this project.**
> Tool-specific files (CLAUDE.md, GEMINI.md, CODEX.md) extend this file with platform-specific guidance.
> If anything in a tool-specific file contradicts this file, **this file wins.**

---

## The Golden Rule

> **"Truth is not merged. Evidence is merged. Truth is recomputed."**

Every event in a Provara vault is cryptographic evidence — signed, hashed, chained. Vaults are append-only. Integrity is verified, never assumed. State is derived by replaying evidence through a deterministic reducer. This is the philosophical and technical foundation of the entire project. Internalize it before writing a single line of code.

---

## Project Identity

| Field | Value |
|-------|-------|
| **Public Brand** | Provara — the open-source protocol and everything the public sees |
| **Parent Entity** | Hunt Information Systems LLC — legal/private entity, NOT promoted publicly |
| **Protocol** | Provara Protocol v1.0 (formerly SNP) |
| **Motto** | Sovereign Memory. Verifiable Continuity. |
| **License** | Apache 2.0 |
| **Repo** | https://github.com/provara-protocol/provara |
| **Design Horizon** | 50-year readability and tamper-evidence |

### Two-Brand Architecture

```
Hunt Information Systems LLC (private layer)
├── Legal entity for contracts, taxes, filings
├── Market intelligence, scanning, proprietary research
├── NOT promoted in public-facing content
│
└── Provara (public layer)
    ├── Open-source protocol, PyPI package, MCP server
    ├── All social media, docs, community, marketing
    ├── Future hosted services + enterprise sales
    └── DBA filed under the LLC
```

**Rule:** All public-facing content (README, docs, social, blog posts, conference talks) uses "Provara" or "the Provara team." "Hunt Information Systems" only appears in legal documents, contracts, and LICENSE files where a registered entity is required. AI agents **must default to "Provara"** in all generated content.

**Quick test:** If a stranger on GitHub will read it → "Provara." If a lawyer or tax authority will read it → "Hunt Information Systems LLC."

---

## Architecture

### Stack Summary

| Layer | Detail |
|-------|--------|
| **Language** | Python 3.10+, cross-platform (Windows, macOS, Linux) |
| **Source** | 7 modules in `SNP_Core/bin/` (~2,016 lines) |
| **Tests** | 110 total: 93 unit + 17 compliance in `SNP_Core/test/` |
| **Dependency** | `cryptography >= 41.0` — **the only external dependency** |
| **Signatures** | Ed25519 (RFC 8032) |
| **Hashing** | SHA-256 (FIPS 180-4) |
| **Serialization** | RFC 8785 canonical JSON (deterministic) |
| **Storage** | NDJSON event streams, append-only |

### Design Principles

1. **Single dependency by design.** The `cryptography` package is the only external import. This is an intentional architectural choice for supply chain minimalism, auditability, and 50-year readability. Everything else is stdlib. Do not introduce new dependencies.

2. **Append-only, tamper-evident.** Events are chained by `prev_hash`. Once written, events are never modified or deleted. Integrity is enforced by cryptographic verification, not access control.

3. **Deterministic replay.** Given the same event log, any compliant implementation must produce the same final state. The reducer is pure — no side effects, no randomness, no system state.

4. **Spec-first development.** `PROTOCOL_PROFILE.txt` is the frozen normative specification. Code conforms to the spec. The spec is never modified to accommodate code.

5. **Cross-platform, cross-language portability.** The protocol is defined by its behavior, not its Python implementation. The 17 compliance tests are the canonical validator — any implementation in any language that passes them is conformant.

---

## Critical Rules

These are non-negotiable. Violating any of these is a session-ending event.

| # | Rule | Why |
|---|------|-----|
| 1 | **NEVER modify `PROTOCOL_PROFILE.txt`** | It is the frozen normative specification. All code conforms to it. |
| 2 | **NEVER commit private keys** | `*_private_keys.json` and `*.key` are gitignored. Leaking keys voids vault integrity. |
| 3 | **NEVER introduce new dependencies** | Single-dep design is architectural. Owner approval required for any exception. |
| 4 | **NEVER use `2>nul` on Windows** | It creates a literal file named `nul`. Always use `2>/dev/null` under Git Bash. |
| 5 | **ALWAYS run tests before claiming done** | Both unit (93) and compliance (17) suites must pass. No exceptions. |
| 6 | **NEVER weaken compliance tests** | They validate the spec. If code fails compliance, fix the code — not the test. |
| 7 | **NEVER output PII** | No real names, personal emails, addresses, locations. See OPSEC section. |
| 8 | **NEVER force push to main** | History is append-only — in the repo too. |

---

## Running Tests

```bash
# All unit tests (93 tests)
cd SNP_Core/test && PYTHONPATH=../bin python -m unittest test_reducer_v0 test_rekey test_bootstrap test_sync_v0 -v

# Compliance tests (17 tests)
cd SNP_Core/test && PYTHONPATH=../bin python backpack_compliance_v1.py ../examples/reference_backpack -v

# Or use the Makefile:
make test          # all 110 tests
make test-unit     # 93 unit tests only
make test-comply   # 17 compliance tests only
```

**Test hierarchy:**
- **Compliance tests are sacred.** They define what "correct" means. Never modify them to make code pass.
- **Unit tests are important.** Every behavioral change ships with a test or an explicit justification.
- **The reference backpack is a fixture.** `SNP_Core/examples/reference_backpack/` is a known-good vault. Don't regenerate it without reason.

---

## Key File Locations

| Path | Purpose | Mutable? |
|------|---------|----------|
| `SNP_Core/bin/` | 7 operational Python modules | ✅ — the codebase |
| `SNP_Core/test/` | 4 test suites + compliance verifier | ⚠️ — add tests, never weaken |
| `SNP_Core/examples/reference_backpack/` | Known-good test fixture | ❌ — frozen unless regenerating |
| `SNP_Core/deploy/templates/` | Policy templates (safety, retention, sync) | ✅ |
| `PROTOCOL_PROFILE.txt` | Frozen protocol spec | ❌ — **NEVER MODIFY** |
| `README.md` | Primary public documentation | ✅ — Provara branding only |
| `TODO.md` | Master task tracker (gitignored, local only) | ✅ — update proactively |
| `CHECKSUMS.txt` | SHA-256 hashes of all kit files | ✅ — regenerate when files change |
| `AGENTS.md` | This file — universal agent instructions | ⚠️ — owner-approved changes only |
| `CLAUDE.md` / `CODEX.md` / `GEMINI.md` | Tool-specific agent configs | ⚠️ — owner-approved changes only |
| `sites/` | Website source files for 3 domains | ✅ — owner domain |

---

## Module Map

### Core Modules (`SNP_Core/bin/`)

| Module | Responsibility | Key Interfaces |
|--------|---------------|----------------|
| `canonical_json.py` | RFC 8785 deterministic JSON serialization | `canonicalize(obj) → bytes` |
| `backpack_integrity.py` | Merkle tree, path safety, SHA-256 file hashing | `compute_merkle_root()`, `hash_file()` |
| `reducer_v0.py` | Deterministic belief reducer (4 namespaces) | `reduce(state, event) → state` |
| `manifest_generator.py` | Manifest + Merkle root generation | `generate_manifest()` |
| `backpack_signing.py` | Ed25519 signing for events and manifests | `sign_event()`, `verify_event()` |
| `rekey_backpack.py` | Key rotation (revocation + promotion) | `rekey()` — atomic rotate |
| `bootstrap_v0.py` | Creates a compliant vault from nothing | `bootstrap()` — genesis event |
| `sync_v0.py` | Union merge, causal chain verification, fencing tokens | `sync()`, `verify_chain()` |

### Module Dependencies (Internal)

```
bootstrap_v0 ──→ backpack_signing ──→ canonical_json
     │                  │
     ▼                  ▼
reducer_v0      backpack_integrity
     │                  │
     ▼                  ▼
sync_v0 ◄──── manifest_generator
     │
     ▼
rekey_backpack ──→ backpack_signing
```

All modules import from stdlib + `cryptography`. No circular dependencies. No module reaches outside `SNP_Core/bin/` for runtime imports.

### Cryptographic Invariants

These are load-bearing. If you touch crypto code, verify all of these still hold:

1. **Chain integrity:** Every event's `prev_hash` equals `SHA-256(canonical_json(previous_event))`.
2. **Signature validity:** Every event's `signature` is a valid Ed25519 signature over `SHA-256(canonical_json(event_without_signature))`.
3. **Key authority:** The signing key must be the active key at the time of signing (not revoked, not a future key).
4. **Deterministic serialization:** `canonical_json(obj)` must produce identical bytes for identical logical objects, across platforms and languages.
5. **Merkle consistency:** `compute_merkle_root()` over the same file set must produce the same root, regardless of file enumeration order.

---

## Multi-Agent Governance

### Agent Roles

This project uses multiple AI coding agents (Claude Code, Codex/ChatGPT, Gemini CLI, Copilot) under owner coordination. Agents do not communicate with each other directly — the owner is the coordinator.

### Coordination Protocol

1. **AGENTS.md is the constitution.** All agents read it. All agents obey it. Conflicts between tool-specific files and AGENTS.md are resolved in favor of AGENTS.md.
2. **TODO.md is the shared task board.** Before starting work, check it. After completing work, update it. If you find something that needs doing, add it.
3. **The codebase is the shared state.** Agents coordinate through committed code, not through messages to each other. Leave clear commit messages. Leave the repo clean.
4. **Don't undo another agent's work** unless it's demonstrably broken (tests fail, spec violation, OPSEC breach). If something looks wrong but tests pass, flag it in TODO.md for the owner.
5. **No territorial claims.** Any agent can work on any module. The module map describes responsibility boundaries, not ownership boundaries.

### Conflict Resolution

If you encounter code from another agent that seems wrong:
1. **Run the tests.** If they pass, the code is presumed correct.
2. **Check PROTOCOL_PROFILE.txt.** If the code violates the spec, flag it.
3. **Check AGENTS.md.** If it violates a critical rule, flag it.
4. **Otherwise, leave it.** Add a note to TODO.md if you have concerns. Don't refactor code you didn't break.

---

## Working Style

### For All Agents

- **Batch and parallelize** — run independent operations concurrently. File reads, searches, and test suites should never be serialized when they have no dependencies.
- **Read before writing** — understand existing code and conventions before proposing changes. Match the patterns already in the codebase.
- **Avoid over-engineering** — no unnecessary abstractions, no speculative features, no premature generalization.
- **Evidence before assertions** — run the actual tests and show output before claiming something works.
- **Maintain TODO.md** — it's the master task tracker. If you notice a gap, missing item, broken assumption, or something the owner might have missed, **add it** under the appropriate phase. Don't wait to be asked. This file is gitignored and local-only.
- **Commit incrementally** — small, atomic commits > one mega-commit. Each commit should be a single logical change that passes all tests.
- **Leave the repo clean** — every session ends with passing tests, no uncommitted changes (unless explicitly work-in-progress), and updated TODO.md.

### Code Standards

- **Imports:** stdlib → third-party → local. One blank line between groups. Alphabetical within groups.
- **Error handling:** Raise exceptions with context. `raise ValueError("Invalid event: missing prev_hash")` not `raise ValueError()`. Never swallow exceptions silently.
- **No dead code.** Don't leave commented-out blocks. Don't leave `pass` stubs without `# TODO` markers.
- **No magic values.** Constants get names. Hash algorithms get referenced by their spec identifier.
- **Docstrings:** Match existing density. Don't auto-generate verbose docstrings on code that currently has none.

---

## Owner Profile

The owner is a **visual-first operator** — thinks in dashboards, websites, and interfaces, not terminal output. Communicate results concisely. Default to the highest-leverage choice rather than listing tradeoffs. The owner's time is spent on business, design, and deployment — not debugging Python.

**What this means in practice:**

- Do not ask for clarification on backend implementation details. Make the right call.
- When something breaks, fix it and explain what happened after — don't present a menu of options.
- Maximize autonomous progress on every invocation. Batch aggressively. Parallelize everything.
- Treat every session as if it may be the only one for a while — leave the codebase in a clean, tested, committable state.
- When presenting results, lead with what changed and what it means — not how you got there.

---

## OPSEC — Anonymity & Remote-First

The owner operates **anonymously behind the LLC.** Hunt Information Systems LLC is the public identity. The founder is invisible. This is a **permanent operational constraint**, not a temporary preference.

### Hard Rules — All Agents, All Sessions

| # | Rule |
|---|------|
| 1 | **NEVER output the owner's real name** in any code, commit, doc, article, social draft, or public content. If you encounter it in existing files, **flag it** — do not propagate. |
| 2 | **NEVER include personal emails, phone numbers, physical addresses, or location details.** No city, state, country, or timezone references that could identify the owner. |
| 3 | **ALWAYS use company voice.** Write as "Hunt Information Systems," "the Provara team," or "the maintainers." Never first-person singular ("I built this"). Use "we" or passive voice for public content. |
| 4 | **Git identity = company identity.** Commits use company name + brand email. Never personal credentials. |
| 5 | **Account registrations use brand email** (`contact@huntinformationsystems.com` or `hello@huntinformationsystems.com`). Never personal email. |
| 6 | **The LLC is the author/seller/maintainer** in all package metadata (`pyproject.toml`, `package.json`, `Cargo.toml`), LICENSE files, and platform registrations. |
| 7 | **Domain WHOIS privacy enabled** on all domain registrations. |
| 8 | **No identifying metadata.** Strip EXIF from images. No personal references in comments or changelogs. |

### OPSEC Violation Response

If you discover a potential OPSEC leak in the codebase (real name in a comment, personal email in config, location reference in a doc):
1. **Do not propagate it.** Don't copy it into your output.
2. **Flag it immediately** to the owner with the file path and line number.
3. **Propose a fix** (redaction, replacement with brand identity).
4. **Check for similar patterns** in other files — leaks tend to cluster.

---

## Division of Labor

```
┌─────────────────────────────────────────┐
│              OWNER DOMAIN               │
│  Websites · Dashboards · Domains        │
│  Business Formation · Marketing         │
│  Deployment · Design · Product Surface  │
└──────────────────┬──────────────────────┘
                   │ coordinates
┌──────────────────▼──────────────────────┐
│             AGENT DOMAIN                │
│  Backend Code · Test Coverage           │
│  Protocol Implementation · Docs         │
│  CI/CD · Code Quality · Tooling         │
│  Cross-language Ports · Spec Writing    │
└─────────────────────────────────────────┘
```

Agents operate with **maximum autonomy** on backend work. The goal: an army of arms behind the scenes while the owner focuses on the product surface. Don't ask permission for implementation decisions — make the right call and document what you did.

**Branding rule for agents:** When generating any public-facing content (README, blog drafts, social posts, docs, release notes), use "Provara" as the brand. "Hunt Information Systems" is reserved for legal contexts only.

---

## Roadmap Priorities

Ordered by strategic importance. Agents should default to working on the highest-priority item that matches their current session context.

| Priority | Item | Status | Notes |
|----------|------|--------|-------|
| **P0** | Test coverage gaps | 🔄 Active | Edge cases: sync conflicts, reducer namespace collisions, key rotation mid-chain, malformed events |
| **P1** | Formal spec document | 📋 Planned | `BACKPACK_PROTOCOL_v1.0.md` — human-readable protocol spec derived from PROTOCOL_PROFILE.txt |
| **P2** | CI pipeline | 🚧 Blocked | GitHub Actions billing issue. Unblock → automate test runs on every push to main |
| **P3** | Cross-language port | 📋 Planned | Rust, Go, or TypeScript implementation passing all 17 compliance tests |
| **P4** | Checkpoint system | 📋 Planned | Signed state materializations for fast replay without full event log scan |
| **P5** | Perception tiering | 📋 Planned | T0–T3 sensor data hierarchy for structured observation events |

**P0 is always safe to work on.** If you're starting a session and don't have a specific task, look at P0 and TODO.md.

---

## Git Conventions

### Branch Strategy
- `main` is the primary and protected branch
- Feature work on short-lived branches when appropriate
- Remote: `origin` → `https://github.com/provara-protocol/provara.git`

### Commit Standards
- **Format:** [Conventional Commits](https://www.conventionalcommits.org/)
- **Subject:** Imperative mood, under 72 characters, scoped when applicable
- **Body:** Explains *why*, not *what* (the diff shows what)
- **Scope examples:** `feat(vault):`, `fix(crypto):`, `test(compliance):`, `docs:`, `chore:`

### Hard Rules
- Do NOT force push to main. Ever.
- Do NOT commit without running tests first. Both suites.
- Do NOT commit private keys, personal emails, or PII. Check your diff.
- CRLF warnings on Windows are expected and harmless — ignore them.

### Commit Message Examples
```
feat(sync): add fencing token validation on merge

Sync now rejects events with stale fencing tokens, preventing
split-brain scenarios in multi-device vault synchronization.

fix(reducer): handle duplicate namespace keys in UPSERT events

Previously, duplicate keys in the same event caused nondeterministic
reducer output depending on dict insertion order. Now raises
ValueError with the offending key name.

test(rekey): add mid-chain rotation regression test

Covers the case where a rekey event appears between two data events
that reference the old key. Validates that chain verification still
passes through the rotation boundary.
```

---

## Anti-Patterns — Don't Do These

- **Don't add dependencies.** The single-dep constraint is architectural, not accidental.
- **Don't wrap stdlib in abstractions.** If `hashlib.sha256` works, use `hashlib.sha256`.
- **Don't restructure the project layout** without explicit owner instruction.
- **Don't create new utility files** for logic that belongs in existing modules.
- **Don't "improve" working code** that wasn't part of the current task.
- **Don't strip context from error messages** for cleaner aesthetics.
- **Don't generate skeleton implementations** full of `pass` or `# TODO` unless explicitly asked for stubs.
- **Don't modify compliance tests** to make code pass. Fix the code.
- **Don't say "I can't"** without offering 2-3 ranked alternatives.
- **Don't speculate about module internals** — read the source.
- **Don't leave the repo dirty.** Clean state, passing tests, updated TODO.md.
