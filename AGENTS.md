# AGENTS.md — Universal Project Instructions for AI Coding Agents

> This file is the single source of truth for any AI CLI tool working on this project.
> Tool-specific files (CLAUDE.md, GEMINI.md, CODEX.md) reference this file.

## Project Identity

- **Public Brand:** Provara — the open-source protocol and everything the public sees
- **Parent Entity:** Hunt Information Systems LLC — legal/private entity, NOT promoted publicly
- **Protocol:** Provara Protocol v1.0 (formerly SNP)
- **Motto:** Sovereign Memory. Verifiable Continuity.
- **License:** Apache 2.0
- **Repo:** https://github.com/huntinformationsystems/provara

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

**Rule:** All public-facing content (README, docs, social, blog posts, conference talks) uses "Provara" or "the Provara team" as the identity. "Hunt Information Systems" only appears in legal documents, contracts, and LICENSE files where a registered entity is required. AI agents must default to "Provara" in all generated content.

## Architecture

- 7 Python modules in `SNP_Core/bin/` (~2,016 lines)
- 110 tests: 93 unit + 17 compliance in `SNP_Core/test/`
- Single dependency: `cryptography >= 41.0`
- Python 3.10+, cross-platform (Windows, macOS, Linux)
- Ed25519 signatures (RFC 8032), SHA-256 hashing (FIPS 180-4), RFC 8785 canonical JSON

## Critical Rules

1. **NEVER modify `PROTOCOL_PROFILE.txt`.** It is the frozen normative specification. All code must conform to it.
2. **NEVER commit private keys.** Any file matching `*_private_keys.json` or `*.key` is gitignored for a reason.
3. **NEVER introduce new dependencies** without explicit user approval. The single-dependency design is intentional.
4. **NEVER use `2>nul` on Windows.** It creates a literal `nul` file. Always use `2>/dev/null`.
5. **ALWAYS run tests** before claiming work is complete. Both unit and compliance suites must pass.

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

## Key File Locations

| File | Purpose |
|------|---------|
| `SNP_Core/bin/` | 7 operational Python modules |
| `SNP_Core/test/` | 4 test suites + compliance verifier |
| `SNP_Core/examples/reference_backpack/` | Known-good test fixture |
| `SNP_Core/deploy/templates/` | Policy templates (safety, retention, sync) |
| `PROTOCOL_PROFILE.txt` | Frozen protocol spec — DO NOT MODIFY |
| `README.md` | Primary documentation |
| `TODO.md` | Master task tracker (gitignored, local only) |
| `CHECKSUMS.txt` | SHA-256 hashes of all kit files |
| `sites/` | Website source files for 3 domains |

## Module Map

| Module | Responsibility |
|--------|---------------|
| `canonical_json.py` | RFC 8785 deterministic JSON serialization |
| `backpack_integrity.py` | Merkle tree, path safety, SHA-256 file hashing |
| `reducer_v0.py` | Deterministic belief reducer (4 namespaces) |
| `manifest_generator.py` | Manifest + Merkle root generation |
| `backpack_signing.py` | Ed25519 signing for events and manifests |
| `rekey_backpack.py` | Key rotation (revocation + promotion) |
| `bootstrap_v0.py` | Creates a compliant vault from nothing |
| `sync_v0.py` | Union merge, causal chain verification, fencing tokens |

## Working Style

- **Batch and parallelize** — run independent operations concurrently. File reads, searches, and test suites should never be serialized when they have no dependencies.
- **Read before writing** — understand existing code and conventions before proposing changes.
- **Respect existing patterns** — match the code style already in the codebase.
- **Avoid over-engineering** — no unnecessary abstractions, no speculative features.
- **Evidence before assertions** — run the actual tests and show output before claiming something works.
- **Maintain TODO.md** — `TODO.md` is the master task tracker. If you notice a gap, missing item, broken assumption, or something the owner might have missed, **add it to TODO.md** under the appropriate phase. Don't wait to be asked. This file is gitignored and local-only — treat it as a living scratchpad for the project.

## Owner Profile

The owner is a **visual-first operator** — thinks in dashboards, websites, and interfaces, not terminal output. Communicate results concisely. When presenting options, default to the highest-leverage choice rather than listing tradeoffs. The owner's time is spent on business, design, and deployment — not debugging Python.

**What this means in practice:**
- Do not ask for clarification on backend implementation details. Make the right call.
- When something breaks, fix it and explain what happened after — don't present a menu of options.
- Maximize autonomous progress on every invocation. Batch aggressively. Parallelize everything.
- Treat every session as if it may be the only one for a while — leave the codebase in a clean, tested, committable state.

## OPSEC — Anonymity & Remote-First

The owner operates **anonymously behind the LLC**. Hunt Information Systems LLC is the public identity. The founder is invisible.

**Hard rules for all AI agents:**

1. **NEVER output the owner's real name** in any code, commit message, documentation, article, social media draft, or public-facing content. If you encounter it in existing files, flag it — do not propagate it.
2. **NEVER include personal email addresses, phone numbers, physical addresses, or location details** in any output. No city, state, country, or timezone references that could identify the owner.
3. **ALWAYS use company voice** — write as "Hunt Information Systems," "the Provara team," or "the maintainers." Never first-person singular ("I built this"). Use "we" or passive voice for public content.
4. **Git identity = company identity.** Commits must use the company name and brand email, never personal credentials.
5. **All account registrations use brand email** (contact@huntinformationsystems.com or hello@huntinformationsystems.com). Never personal email.
6. **The LLC is the author, seller, and maintainer** in all package metadata (pyproject.toml, package.json, Cargo.toml), LICENSE files, and platform registrations.
7. **Domain WHOIS privacy enabled** on all domain registrations.
8. **No identifying metadata** — strip EXIF data from images, avoid personal references in comments or changelogs.

**Why this matters:** The owner works remotely and location-independently. The LLC is the shield between the project and the person. This is a permanent operational constraint, not a temporary preference. Every session, every commit, every public artifact must respect this boundary.

## Division of Labor

The owner handles: websites, dashboards, domains, business formation, marketing, and deployment.

AI agents handle: backend code, test coverage, protocol implementation, documentation, CI/CD, and code quality. Agents should operate with maximum autonomy on backend work — the goal is an army of arms behind the scenes while the owner focuses on the product surface.

**Branding rule for agents:** When generating any public-facing content (README text, blog drafts, social posts, documentation, release notes), use "Provara" as the brand. Do NOT use "Hunt Information Systems" in public content. The LLC name is reserved for legal contexts only (LICENSE files, contract templates, legal notices).

## Roadmap Priorities (for AI agents)

1. Test coverage gaps — edge cases for sync, reducer conflicts, key rotation
2. Cross-language reimplementation — Rust, Go, or TypeScript passing 17 compliance tests
3. Formal spec document — `BACKPACK_PROTOCOL_v1.0.md`
4. Checkpoint system — signed state materializations for fast replay
5. Perception tiering — T0–T3 sensor data hierarchy
6. CI pipeline — fix GitHub Actions billing, unblock automation

## Git Conventions

- Branch: `main` is the primary branch
- Remote: `origin` → `https://github.com/huntinformationsystems/provara.git`
- Commit style: imperative mood, concise subject, body explains why
- Do NOT force push to main
- Do NOT commit without running tests first
- CRLF warnings on Windows are expected and harmless
