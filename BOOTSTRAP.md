# Provara Protocol — AI Agent Bootstrap Prompt

**Copy/paste this at the start of every session.**

---

## Project Identity

**Provara Protocol v1.0.0** — Tamper-evident memory substrate for AI systems, sovereign identity, and long-lived digital institutions.

**Motto:** *"Truth is not merged. Evidence is merged. Truth is recomputed."*

**License:** Apache 2.0 | **Repo:** `github.com/provara-protocol/provara` | **Status:** ✅ Stable Release (2026-02-17)

---

## Current State (Post-Launch)

| Metric | Value |
|--------|-------|
| **Version** | 1.0.0 (stable) |
| **Tests** | 222 passing (125 unit + 8 vector + 17 compliance + 60 PSMC + 22 MCP) |
| **Dependencies** | 1 external: `cryptography>=41.0` |
| **Core modules** | 7 Python files in `SNP_Core/bin/` |
| **Spec** | Frozen (`PROTOCOL_PROFILE.txt`) + HTML (`docs/BACKPACK_PROTOCOL_v1.0.html`) |

---

## Repo Layout

```
provara/
├── SNP_Core/bin/          # Core protocol (7 modules)
│   ├── canonical_json.py  # RFC 8785 + SHA-256
│   ├── backpack_signing.py # Ed25519 sign/verify
│   ├── reducer_v0.py      # 4-namespace belief reducer
│   ├── sync_v0.py         # Union-merge + fencing tokens
│   ├── rekey_backpack.py  # Key rotation protocol
│   ├── bootstrap_v0.py    # Vault initialization
│   └── backpack_integrity.py # Merkle tree + manifest
├── tools/
│   ├── psmc/              # Personal Sovereign Memory Container (60 tests)
│   └── mcp_server/        # MCP server (22 tests, stdio + SSE)
├── docs/
│   ├── BACKPACK_PROTOCOL_v1.0.html  # Static HTML spec (50-year artifact)
│   ├── BACKPACK_PROTOCOL_v1.0.md    # Human-readable spec
│   └── SPEC_DECISIONS.md            # 8 resolved spec decisions
└── test_vectors/          # Cross-language test vectors
```

---

## Active Lanes (TODO.md)

### Lane 1: Protocol Finalization
- [x] Spec hardening ✅
- [ ] **Spec publication** — Owner: deploy provara.dev, assign version-locked URL
- [ ] Extension registry process
- [ ] IANA-style considerations stub

### Lane 2: Reference Implementation Maturity
- [ ] **mypy --strict passing** (high priority)
- [ ] Package layout restructure (`src/provara_protocol/`)
- [ ] API docs (mkdocs)
- [ ] CLI consolidation (in progress)

### Lane 3: Cross-Language Credibility
- [ ] Rust port (`provara-rs`)
- [ ] TypeScript port
- [ ] Go port

### Lane 4: Integration & Distribution
- [x] MCP server v1 ✅ (22 tests, full tool surface)
- [x] PSMC v1.1 ✅ (reducer, sync, checkpoint)
- [ ] Demo: Claude agent with Provara vault memory
- [ ] GitHub Action (`provara-action`)

### Lane 5: Business & GTM (Owner-only)
- [ ] LLC formation, domain acquisition, PyPI publish
- [ ] Show HN, Dev.to, Reddit, LinkedIn

### Lane 6: Community & Ecosystem
- [ ] GitHub Discussions, PR reviews
- [ ] "Good first issue" labels

---

## Non-Negotiable Rules

1. **OPSEC:** Never output real names, personal emails, addresses, or locations. Public brand = "Provara". Legal entity = "Hunt Information Systems LLC" (private).

2. **Single dependency:** `cryptography>=41.0` is the only external dep in `SNP_Core`. No exceptions.

3. **Spec is frozen:** Never modify `PROTOCOL_PROFILE.txt`. Code conforms to spec, not vice versa.

4. **Read before write:** Always read existing code before proposing changes. Match existing patterns.

5. **Test everything:** Every behavioral change ships with a test. Run full suite before committing.

6. **Atomic commits:** Small, logical commits. Conventional Commits format. Include Co-Authored-By for multi-agent work.

7. **No dead code:** Don't leave commented blocks, `pass` stubs without `# TODO`, or unused imports.

---

## Multi-Agent Coordination

**Active agents:** Claude Opus (coordinator), OpenClaw, Gemini CLI, Codex, Qwen

**Coordination protocol:**
1. Read `TODO.md` before starting work
2. Pick first unblocked item in your lane
3. Update `TODO.md` with completion + commit hash
4. Don't undo another agent's work unless tests fail or spec violation
5. Flag concerns in `TODO.md` for owner review

**Lock workflow (for file edits):**
```bash
python tools/check_locks.py claim --agent <name> --name <task> --paths <files>
# ... do work ...
python tools/check_locks.py release --name <task>
```

---

## Test Commands

```bash
# Core unit tests (125)
cd SNP_Core/test && set PYTHONPATH=../bin && python -m unittest test_reducer_v0 test_rekey test_bootstrap test_sync_v0

# Cross-language vectors (8)
cd SNP_Core/test && set PYTHONPATH=../bin && python test_vectors.py

# Compliance tests (17)
cd SNP_Core/test && set PYTHONPATH=../bin && python backpack_compliance_v1.py ../examples/reference_backpack

# PSMC (60)
cd provara && python -m pytest tools/psmc/test_psmc.py -q

# MCP server (22)
cd tools/mcp_server && python -m pytest test_server.py -q

# All tests (222)
cd provara && pytest
```

---

## Immediate Next Actions (Pick One)

**High priority (agent-delegatable):**
1. **mypy --strict passing** (Lane 2B) — Type safety is a security property
2. **Extension registry process** (Lane 1B) — Formalize custom event type proposals
3. **Package layout restructure** (Lane 2B) — `src/provara_protocol/` layout
4. **API docs (mkdocs)** (Lane 2B) — Auto-generated docs at provara.dev/docs

**Owner-only (do not attempt):**
- GitHub Actions billing unblock
- Domain acquisitions (provara.ai, provara.com)
- PyPI publish
- Show HN launch

---

## Cryptographic Invariants

If you touch crypto code, verify these hold:

1. **Chain integrity:** `event.prev_hash == SHA-256(canonical_json(previous_event))`
2. **Signature validity:** `event.sig` is valid Ed25519 over `SHA-256(canonical_json(event_without_sig))`
3. **Key authority:** Signing key must be active (not revoked) at time of signing
4. **Deterministic serialization:** `canonical_json(obj)` produces identical bytes across platforms
5. **Merkle consistency:** Same file set → same root, regardless of enumeration order

---

## Session Hygiene

**Start of session:**
1. Read this bootstrap prompt
2. Read `TODO.md` for current state
3. Pick unblocked task
4. Claim lock if editing files

**End of session:**
1. Run full test suite
2. Update `TODO.md` with completion + commit hash
3. Leave repo in clean, committable state
4. Release any locks held

---

## Quick Reference

| File | Purpose | Mutable? |
|------|---------|----------|
| `PROTOCOL_PROFILE.txt` | Frozen spec | ❌ NEVER |
| `TODO.md` | Task tracker | ✅ Yes (gitignored) |
| `AGENTS.md` | Agent coordination | ⚠️ Owner-approved only |
| `SNP_Core/bin/*.py` | Core protocol | ✅ Yes (with tests) |
| `docs/BACKPACK_PROTOCOL_v1.0.html` | Static HTML spec | ⚠️ Spec changes only |

---

**Start every session here. Pick a task. Execute. Update TODO.md. Commit.**

*"The moat is the spec, not the code."*
