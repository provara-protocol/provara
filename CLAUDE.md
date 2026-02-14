# CLAUDE.md — Claude Code Project Instructions

> Full project context is in **AGENTS.md**. Read it first. This file adds Claude-specific guidance.

## Claude-Specific

- This file is auto-loaded by Claude Code on every session. AGENTS.md is not — read it explicitly at the start of any substantive work.
- Use the Task tool with parallel subagents for independent operations (file searches, test runs, multi-file edits).
- Use Glob/Grep directly for targeted searches; use the Explore agent for broad codebase questions.
- When creating commits, always use the HEREDOC pattern for commit messages.
- On Windows, this repo runs under Git Bash. Use `/c/huntinformationsystems` paths in Bash, `C:\huntinformationsystems` paths in Read/Write/Edit tools.
- Persistent memory is at `C:\Users\c8324\.claude\projects\C--huntinformationsystems\memory\MEMORY.md` — update it when you learn something that should survive across sessions.
- The old `C--HuntOS` memory directory is orphaned and can be ignored.
