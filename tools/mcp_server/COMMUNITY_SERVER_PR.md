# MCP Community Server Submission — Provara Vault

**PR Title:** Add Provara Vault — Cryptographically verified memory for AI agents

**Target Repository:** modelcontextprotocol/servers (or MCP Registry)

**Date:** 2026-02-18

---

## PR Description

### What It Does (3 sentences)

Provara Vault is an MCP server that provides AI agents with cryptographically verified, tamper-evident memory. Every event appended to a Provara vault is signed with Ed25519, linked via SHA-256 hash chains, and integrity-verified via Merkle trees—making it impossible to silently alter an agent's memory. Unlike standard MCP Memory, Provara provides multi-actor support, cryptographic audit trails, and 50-year readability guarantees.

### Why It's Different from MCP Memory

| Feature | MCP Memory | Provara Vault |
|---------|------------|---------------|
| **Integrity** | Database ACID | Ed25519 signatures + hash chains |
| **Tamper evidence** | No | Yes (Merkle tree verification) |
| **Multi-actor** | Single user | Multiple actors with separate chains |
| **Audit trail** | Logs (mutable) | Cryptographic event log (immutable) |
| **Long-term storage** | Database format | Plain text NDJSON (50-year readability) |
| **Compliance** | None | GDPR Article 17 (crypto-shredding) |

### Installation

```bash
pip install provara-protocol[mcp]
```

### Configuration for Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "provara": {
      "command": "python",
      "args": ["-m", "provara.mcp", "--transport", "stdio"],
      "env": {
        "PROVARA_VAULT_PATH": "/path/to/your/vault"
      }
    }
  }
}
```

### Links

- **Repository:** https://github.com/provara-protocol/provara
- **Documentation:** https://provara-protocol.github.io/provara/
- **Playground:** https://provara-protocol.github.io/provara/
- **PyPI:** https://pypi.org/project/provara-protocol/
- **IETF Internet-Draft:** https://datatracker.ietf.org/doc/draft-hunt-provara-protocol/

---

## README Addition (for Community Servers List)

### Exact Text to Add

```markdown
### Provara Vault
Cryptographically verified memory for AI agents. Ed25519 signed,
tamper-evident, multi-actor event logs with causal chain integrity.

- **Tools:** `init_vault`, `append_event`, `verify_vault`, `query_events`,
  `forensic_export`, `checkpoint_vault`, `export_markdown`, `list_conflicts`,
  `generate_digest`, `verify_chain`, `snapshot_state`, `query_timeline`,
  `check_safety`, `scitt_export` (14 tools)
- **Resources:** `vault://events`, `vault://status`
- **Install:** `pip install provara-protocol[mcp]`
- **Repo:** [provara-protocol/provara](https://github.com/provara-protocol/provara)
- **Docs:** [Provara Documentation](https://provara-protocol.github.io/provara/)
```

### Where to Add

Insert alphabetically under "P" in the community servers list, or submit via the MCP Registry at https://modelcontextprotocol.io/registry.

---

## MCP Registry Submission (server.json)

For the official MCP Registry, prepare:

```json
{
  "name": "io.github.provara-protocol/provara-vault",
  "location": "pypi:provara-protocol[mcp]",
  "description": "Cryptographically verified memory for AI agents with tamper-evident event logs",
  "capabilities": {
    "tools": [
      "init_vault",
      "append_event",
      "verify_vault",
      "query_events",
      "forensic_export",
      "checkpoint_vault",
      "export_markdown",
      "list_conflicts",
      "generate_digest",
      "verify_chain",
      "snapshot_state",
      "query_timeline",
      "check_safety",
      "scitt_export"
    ],
    "resources": [
      "vault://events",
      "vault://status"
    ]
  },
  "execution": {
    "command": "python",
    "args": ["-m", "provara.mcp", "--transport", "stdio"],
    "env": {
      "PROVARA_VAULT_PATH": "${VAULT_PATH}"
    }
  },
  "repository": "https://github.com/provara-protocol/provara",
  "documentation": "https://provara-protocol.github.io/provara/",
  "version": "1.0.1"
}
```

---

## Screenshot/Demo Requirements

### Recommended Screenshots

1. **Claude Creating a Vault**
   - Show Claude running `provara init my-vault` via MCP
   - Display the genesis event creation
   - Show the Ed25519 keypair generation output

2. **Claude Appending Events**
   - Show natural language: "Remember that I prefer Python over JavaScript"
   - Display the signed event being appended
   - Show the event_id and signature

3. **Claude Querying Memory**
   - Show: "What do I prefer for programming?"
   - Display the query returning the signed event
   - Show verification status

4. **Terminal Verification**
   - Run `provara verify my-vault`
   - Show "PASS: All 17 integrity checks passed"
   - Display the Merkle root and chain verification

### Demo GIF Script (30 seconds)

```
[0:00-0:05]  Terminal: pip install provara-protocol[mcp]
[0:05-0:10]  Claude Desktop: "Initialize a new Provara vault"
[0:10-0:15]  Terminal: provara init ~/vaults/claude-memory
[0:15-0:20]  Claude: "Remember my API key is sk-xxxx"
[0:20-0:25]  Terminal: provara verify ~/vaults/claude-memory
[0:25-0:30]  Output: "PASS: All 17 integrity checks passed"
```

### Where to Host

- Upload to `/content/screenshots/` in the repo
- Host on Imgur for PR description
- Embed in README.md

---

## Namespace Authentication

For MCP Registry submission, authenticate the namespace:

**Option A: GitHub Authentication**
- Use `io.github.provara-protocol` namespace
- Verify via GitHub organization membership

**Option B: DNS Authentication**
- Use `dev.provara` namespace
- Add TXT record to DNS

**Option C: HTTP Authentication**
- Host verification file at `https://provara.dev/.well-known/mcp-registry`

---

## PR Checklist

- [ ] Server is publicly accessible (PyPI package)
- [ ] Namespace ownership verified
- [ ] `server.json` passes validation
- [ ] README addition follows format
- [ ] Screenshots/demo included
- [ ] Installation instructions tested
- [ ] Claude Desktop config documented
- [ ] Links to docs and playground working

---

## Follow-up Actions

After PR merge:

1. **Announce on MCP Discord** — #community-servers channel
2. **Update Provara README** — Add MCP Registry badge
3. **Blog post** — "Provara Vault is now an MCP Community Server"
4. **Social media** — Twitter, LinkedIn, Mastodon

---

*This document is part of Provara v1.0. For questions about the submission process, contact the MCP steering group or open an issue.*
