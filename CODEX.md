# CODEX.md — OpenAI Codex / ChatGPT / GitHub Copilot

> Full project context is in **AGENTS.md**. Read it first. That file is the single source of truth for all AI coding agents on this project.

---

## Bootstrap Sequence

1. **Read AGENTS.md first.** It contains the module map, roadmap, critical rules, OPSEC policy, and brand architecture. Everything else is a supplement.
2. **Read TODO.md** before starting work. If you spot gaps, missing items, or things the owner might have missed, add them to the appropriate phase. Don't wait to be asked. TODO.md is gitignored and local-only.
3. If the task touches a specific module, read that module's source before proposing changes. Understand before you edit.

---

## Environment

| Context | Detail |
|---------|--------|
| **OS** | Windows (Git Bash) / Cross-platform target |
| **Python** | 3.10+ — single dependency: `cryptography>=41.0` |
| **Test runner** | `pytest` — 110 tests (93 unit + 17 compliance) |
| **Repo** | `github.com/provara-protocol/provara` |
| **License** | Apache 2.0 |

---

## Codex / ChatGPT Operational Notes

### Context Window Management
- This project's full context lives in AGENTS.md. If you're operating in a chat session, request that file explicitly if you need module maps, roadmap phases, or architectural decisions.
- Don't hallucinate file paths or module names. If you're unsure of the project structure, ask or reference AGENTS.md.
- When given a task, scope your response to what's actually asked. Don't refactor adjacent code unless instructed.

### GitHub Copilot — Inline Completion Rules
- **Match existing patterns.** This codebase has specific conventions for Ed25519 key handling, SHA-256 chain hashing, RFC 8785 canonical JSON, and NDJSON event streams. Follow what's already there.
- **Don't auto-complete imports for packages that aren't dependencies.** The project has exactly one external dependency: `cryptography>=41.0`. If Copilot suggests importing `pynacl`, `orjson`, `pydantic`, or anything else — reject it.
- **Don't generate boilerplate docstrings** on functions that don't already have them. Match the existing documentation density.
- **Type hints follow existing conventions.** Check nearby code before adding or changing type annotations.

### Code Generation Standards
- **Surgical edits over full rewrites.** If the task is "fix this function," return the fixed function — not the entire file rewritten with your preferred style.
- **Imports stay sorted.** stdlib → third-party → local. One blank line between groups.
- **Error handling is explicit.** Raise exceptions with context. Don't return None and hope for the best. Cryptographic operations especially get full validation.
- **Every behavioral change needs a test** or a clear justification for why not.

---

## Code Standards

### The Dependency Rule
This project has **one** external dependency: `cryptography>=41.0`. That's intentional — it's designed for 50-year readability and minimal supply chain attack surface. Do not:
- Suggest adding new dependencies
- Import from packages that aren't installed
- Wrap stdlib functions in third-party abstractions

### Cryptographic Discipline
- Ed25519 for signatures. SHA-256 for hashing. RFC 8785 for canonical JSON. These are not suggestions — they're the spec.
- Never weaken cryptographic parameters to "simplify" code.
- Validate inputs. Verify signatures. Check chain hashes. Trust nothing.

### Testing
- `pytest` runs the full suite. Compliance tests validate the Provara specification — they are **sacred** and must never be weakened to make code pass.
- If you're generating test code, follow existing test patterns. Check `tests/` for conventions before writing new tests.

---

## Operational Rules

### OPSEC — Non-Negotiable
Read the full "OPSEC — Anonymity & Remote-First" section in AGENTS.md. The short version:
- **Never output real names, personal emails, physical addresses, or location details.** Not in code, comments, commit messages, docs, or error messages.
- If you're generating content that will be committed to the repo, sanitize it. If you're unsure whether something is PII, treat it as PII.

### Two-Brand Architecture
- **"Provara"** → public brand. All public-facing content: README, docs, PyPI, website, community materials.
- **"Hunt Information Systems LLC"** → private legal entity. Only in LICENSE files, legal documents, contracts.
- Default to "Provara" for anything a stranger on GitHub would see.

### Destructive Actions
Flag these for owner confirmation — never execute autonomously:
- Deleting files or removing code blocks you don't fully understand
- Changing cryptographic parameters (algorithms, key sizes, hash functions)
- Modifying the event schema or vault format
- Removing or weakening tests

### The Golden Rule
> **"Truth is not merged. Evidence is merged. Truth is recomputed."**

This is the core design philosophy. Every event is evidence. Vaults are append-only. Integrity is verified, not assumed.

---

## Anti-Patterns — Don't Do These

- Don't add dependencies. Period.
- Don't restructure the project layout without explicit instruction.
- Don't create new utility modules for things that belong in existing files.
- Don't "improve" working code that wasn't part of the task.
- Don't strip error context from exceptions to make code "cleaner."
- Don't generate placeholder implementations with `# TODO` unless explicitly asked for stubs.
- Don't say "I can't" without offering 2-3 ranked alternatives.

---

## Commit Message Format

If generating commit messages, use [Conventional Commits](https://www.conventionalcommits.org/):
```
feat(vault): add tamper-detection to seal verification
fix(crypto): handle malformed Ed25519 public keys gracefully
test(compliance): add chain integrity regression tests
docs: update README with vault usage examples
```

Scope to the module when applicable. Keep the subject line under 72 characters. Body explains *why*, not *what* (the diff shows what).
