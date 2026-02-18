# CLAUDE.md — Claude Code Project Instructions

> Full project context is in **AGENTS.md**. Read it first. This file adds Claude-specific operational guidance.

---

## Bootstrap Sequence

1. **This file auto-loads every session.** AGENTS.md does not — read it explicitly at the start of any substantive work.
2. **Read TODO.md** before touching code. If you spot gaps, missing items, or things the owner might have missed, add them to the appropriate phase. Don't wait to be asked.
3. **Read MEMORY.md** at `$HOME\.claude\projects\C--provara\memory\MEMORY.md` — it contains cross-session learnings. Update it when you discover something that should persist.
4. If the task touches a specific module, read that module's code before proposing changes. Read-before-write, always.

---

## Prompt Self-Enhancement

Before acting on any user prompt, internally apply these prompt engineering principles to sharpen your interpretation:

1. **Decompose** — Break vague or compound requests into discrete, actionable sub-tasks before executing.
2. **Steelman** — Infer the strongest version of the user's intent. If they say "fix the tests," they mean diagnose root cause, fix, and verify — not just silence the error.
3. **Constraint extraction** — Identify implicit constraints (OPSEC, single-dep rule, spec compliance, existing patterns) that the user didn't restate but that apply.
4. **Edge-case scan** — Before implementing, mentally enumerate failure modes, boundary conditions, and security implications. Address the important ones proactively.
5. **Chain of thought** — For non-trivial tasks, reason through your approach step-by-step before writing code. Show your work when it adds clarity; internalize it when it doesn't.
6. **Scope discipline** — Do exactly what was asked, enhanced by the above. Don't let enhancement become scope creep.

This is not a separate step you announce — it's how you process every request.

---

## Environment

| Context | Detail |
|---------|--------|
| **OS** | Windows — repo runs under **Git Bash** |
| **Bash paths** | `/c/provara/...` |
| **Read/Write/Edit paths** | `C:\provara\...` |
| **Python** | 3.10+ — single dependency: `cryptography>=41.0` |
| **Test runner** | `pytest` — 110 tests (93 unit + 17 compliance) |
| **Repo** | `github.com/provara-protocol/provara` |
| **License** | Apache 2.0 |

---

## Tool Usage — Tactical

### Parallel Subagents (Task Tool)
Use the Task tool aggressively for independent operations. If three files need searching, three tests need running, or three edits are independent — **fan out, don't serialize.**

Good candidates for parallel dispatch:
- Running tests while reading related source files
- Searching for usages across multiple modules simultaneously
- Validating multiple file formats or schemas at once
- Cross-referencing TODO.md, AGENTS.md, and source in one pass

### Search Strategy
- **Glob/Grep** → targeted, known-pattern searches (function names, imports, string literals)
- **Explore agent** → broad codebase questions ("how does vault sealing work?", "where is Ed25519 signing invoked?")
- **Read tool** → when you know the exact file, read it directly. Don't grep for what you can open.

### Commits
Always use the **HEREDOC pattern** for commit messages:
```bash
git commit -m "$(cat <<'EOF'
feat: add tamper-detection to vault seal verification

- Validate chain integrity on unseal
- Reject events with mismatched prev_hash
- Add 4 regression tests for corrupt chain scenarios
EOF
)"
```

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/). Scope to the module when applicable: `feat(vault):`, `fix(crypto):`, `test(compliance):`, etc.

---

## Code Standards

### Read-Before-Write
Match existing patterns. This project has a specific style — Ed25519 key handling, canonical JSON via RFC 8785, NDJSON event streams, SHA-256 chain hashing. Don't introduce new patterns without justification. If the codebase uses `hashlib.sha256`, don't import a wrapper.

### Edits
- **Surgical diffs over full rewrites.** If you're changing 3 lines in a 200-line file, change 3 lines.
- **Never delete code you don't understand.** If something looks dead, flag it — don't remove it silently.
- **Imports stay sorted.** stdlib → third-party → local. One blank line between groups.

### Testing
- Every behavioral change ships with a test or an explicit justification for why not.
- Run the full suite (`pytest`) before any commit. If tests break, fix them before moving on.
- Compliance tests are sacred — they validate the Provara spec. Never weaken them to make code pass.

### Error Handling
- Fail loud, not silent. Raise exceptions with context, don't return None and hope someone checks.
- Cryptographic operations get explicit validation. Don't trust inputs — verify signatures, check chain hashes, validate key formats.

---

## Operational Rules

### OPSEC — Non-Negotiable
Read the full "OPSEC — Anonymity & Remote-First" section in AGENTS.md. The short version:
- **Never output real names, personal emails, physical addresses, or location details.** Not in commits, not in comments, not in generated docs, not in error messages.
- Git author config is already set correctly. Don't touch it.
- If you're unsure whether something is PII, treat it as PII.

### Two-Brand Architecture
- **"Provara"** → public brand. All public-facing content, docs, README, PyPI, community.
- **"Hunt Information Systems LLC"** → private legal entity. Only appears in LICENSE files, legal docs, contracts.
- When in doubt, use "Provara." If you're writing something a stranger on GitHub will read, it says "Provara."

### Destructive Actions
Any of the following require explicit owner confirmation before execution:
- Deleting files or directories
- Force-pushing branches
- Rewriting git history
- Removing tests
- Changing cryptographic parameters (key sizes, algorithms, hash functions)
- Modifying the event schema

### The Golden Rule
> **"Truth is not merged. Evidence is merged. Truth is recomputed."**

This is the Provara design philosophy. Every event is evidence. The vault is append-only. Integrity is verified, not assumed. Keep this in mind when designing anything that touches the event log.

---

## Anti-Patterns — Don't Do These

- Don't add dependencies. The project has **one** external dep (`cryptography>=41.0`). That's by design.
- Don't wrap stdlib in abstractions. If `hashlib.sha256` works, use `hashlib.sha256`.
- Don't generate boilerplate docstrings on existing code that doesn't have them — match the existing documentation density.
- Don't restructure the project layout without explicit instruction.
- Don't create new files for utilities that belong in existing modules.
- Don't say "I can't" without offering 2-3 ranked alternatives.

---

## Session Hygiene

- **Start of session:** Read AGENTS.md → Read TODO.md → Read MEMORY.md → Orient to the task.
- **During work:** Commit incrementally. Small, atomic commits > one mega-commit.
- **End of session:** Update MEMORY.md with anything learned. Update TODO.md if items were completed or discovered. Leave the repo in a clean, committable state.
