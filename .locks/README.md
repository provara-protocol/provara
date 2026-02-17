# `.locks/` Coordination Convention

Purpose: prevent overlapping edits when multiple agents work in parallel.

## Rules

1. Before editing files, check locks:
   - `python tools/check_locks.py check --agent <agent> --paths <path1> <path2>`
2. Claim paths before edits:
   - `python tools/check_locks.py claim --agent <agent> --name <lock_name> --paths <path1> <path2>`
3. Release lock when done:
   - `python tools/check_locks.py release --name <lock_name>`
4. Keep lock scope narrow (only files/dirs you will edit).
5. If a lock is stale, coordinate with owner before force-releasing.

## Lock file format

Each lock is a JSON file: `.locks/<name>.lock`

```json
{
  "agent": "Codex",
  "created_at": "2026-02-17T22:10:00Z",
  "paths": ["tools/mcp_server", "docs/OPEN_DECISIONS.md"],
  "note": "Implement MCP transport"
}
```

## Optional Git Pre-Commit Guard

To prevent accidental commits while locks are still active, enable the repo hook path once per clone:

```bash
git config core.hooksPath .githooks
```

The included `.githooks/pre-commit` hook blocks commits when any `.locks/*.lock` files exist.
