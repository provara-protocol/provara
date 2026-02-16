# GEMINI.md — Gemini CLI / Google AI Studio

> Full project context is in **AGENTS.md**. Read it first. That file is the single source of truth for all AI coding agents on this project.

---

## Bootstrap Sequence

1. **Read AGENTS.md first.** It contains the module map, roadmap, critical rules, OPSEC policy, and brand architecture. No exceptions.
2. **Read TODO.md** before starting work. If you spot gaps, missing items, or things the owner might have missed, add them to the appropriate phase. Don't wait to be asked. TODO.md is gitignored and local-only.
3. If the task touches a specific module, read that module's source before proposing changes. Understand the existing patterns, then match them.

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

## Gemini-Specific Operational Notes

### Context & Grounding
- **AGENTS.md is your ground truth.** If you're unsure about project structure, module responsibilities, or architectural decisions, re-read it before speculating.
- Don't confabulate file paths, function names, or module relationships. If you haven't read the source, say so and read it.
- When the owner gives you a task, check whether AGENTS.md or TODO.md already has relevant context before asking clarifying questions that are already answered.

### Gemini CLI — Shell Integration
- This repo runs under **Git Bash on Windows**. Paths use forward slashes in Bash (`/c/huntinformationsystems/...`).
- When generating shell commands, target Bash syntax. Don't emit PowerShell unless explicitly asked.
- `pytest` is the test runner. Run the full suite before claiming anything works.

### Google AI Studio — Session Notes
- If operating in AI Studio with file uploads, verify you have the latest versions of key files (AGENTS.md, TODO.md, and any module you're editing).
- Long conversations drift. If a session exceeds ~10 exchanges on a complex task, re-anchor to AGENTS.md and the specific module source to avoid accumulated context errors.
- When generating multi-file changes, present them as a clear sequence: which file, what change, why. Don't interleave edits across files in a single code block.

---

## Code Standards

### Read-Before-Write
This project has strong conventions. Before writing or editing code:
- Check how Ed25519 keys are handled in existing modules
- Check how SHA-256 chain hashing is implemented
- Check how RFC 8785 canonical JSON serialization is done
- Check how NDJSON event streams are read and written

Then **match those patterns exactly.** Don't introduce alternative approaches.

### The Dependency Rule
This project has **one** external dependency: `cryptography>=41.0`. That's a deliberate architectural choice for supply chain minimalism and 50-year readability. Do not:
- Suggest adding new packages (no `pydantic`, no `orjson`, no `attrs`, no `click`)
- Import from anything not in stdlib or `cryptography`
- Wrap stdlib in third-party convenience layers

### Edits & Style
- **Surgical diffs over full rewrites.** Change what needs changing. Leave the rest alone.
- **Imports stay sorted.** stdlib → third-party → local. One blank line between groups.
- **Don't auto-generate docstrings** on functions that don't have them. Match existing documentation density.
- **Don't refactor adjacent code** that isn't part of the task.

### Error Handling
- Exceptions carry context. `raise ValueError("Invalid event: missing prev_hash field")` not `raise ValueError("bad input")`.
- Cryptographic operations get explicit input validation. Verify signatures, check key formats, validate chain hashes. Trust nothing.
- Fail loud. Never swallow exceptions or return None where an error should propagate.

### Testing
- Every behavioral change ships with a test.
- Compliance tests validate the Provara spec — they are **sacred.** Never modify them to make implementation code pass. Fix the implementation.
- Follow existing test patterns in `tests/`. Read a few tests before writing new ones.

---

## Operational Rules

### OPSEC — Non-Negotiable
Read the full "OPSEC — Anonymity & Remote-First" section in AGENTS.md. Summary:
- **Never output real names, personal emails, physical addresses, or location details.** This applies to code, comments, commit messages, documentation, error strings, and any generated content.
- If you're producing content that will be committed, pushed, or published — sanitize it.
- When in doubt about whether something is PII, treat it as PII.

### Two-Brand Architecture
- **"Provara"** → public brand. README, docs, PyPI, website, community, anything a stranger sees.
- **"Hunt Information Systems LLC"** → private legal entity. LICENSE headers, contracts, legal docs only.
- Default is always "Provara." Don't reference Hunt Information Systems in public-facing content.

### Destructive Actions — Owner Confirmation Required
Never execute these autonomously:
- Deleting files, directories, or significant code blocks
- Changing cryptographic algorithms, key sizes, or hash functions
- Modifying the event schema or vault format
- Removing or weakening existing tests
- Rewriting git history or force-pushing

### The Golden Rule
> **"Truth is not merged. Evidence is merged. Truth is recomputed."**

Every event is cryptographic evidence. Vaults are append-only. Chain integrity is verified, never assumed. If you're designing anything that touches the event log, internalize this principle first.

---

## Anti-Patterns — Don't Do These

- Don't add dependencies. The single-dep constraint is architectural, not accidental.
- Don't restructure project layout without explicit instruction.
- Don't create new utility files for logic that belongs in existing modules.
- Don't "improve" working code that wasn't part of the task.
- Don't strip context from error messages for aesthetics.
- Don't generate skeleton implementations full of `pass` or `# TODO` unless explicitly asked for stubs.
- Don't say "I can't" without offering 2-3 ranked alternatives.
- Don't speculate about module internals — read the source.

---

## Commit Message Format

If generating commit messages, use [Conventional Commits](https://www.conventionalcommits.org/):
```
feat(vault): add tamper-detection to seal verification
fix(crypto): handle malformed Ed25519 public keys gracefully
test(compliance): add chain integrity regression tests
docs: update README with vault usage examples
```

Scope to the module when applicable. Subject line under 72 characters. Body explains *why*, not *what*.
