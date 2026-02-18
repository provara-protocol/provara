# Provara Tutorials

**Learn Provara in under 25 minutes total.**

Each tutorial is standalone and takes ~5 minutes. Complete them in order for a progressive learning experience, or jump to the one that matches your use case.

---

## Tutorial Series

| # | Tutorial | Time | Focus |
|---|----------|------|-------|
| 1 | [Your First Vault](01_first_vault.md) | 4 min | Create vault, append events, verify chain |
| 2 | [Multi-Actor Dispute](02_multi_actor_dispute.md) | 5 min | Conflicting observations, attestation resolution |
| 3 | [Checkpoint & Query](03_checkpoint_query.md) | 4 min | Fast state recovery, event queries |
| 4 | [MCP Integration](04_mcp_integration.md) | 5 min | AI agent memory via Model Context Protocol |
| 5 | [Anchor to L2](05_anchor.md) | 4 min | RFC 3161 timestamps, blockchain anchoring |

---

## Learning Paths

### For Developers New to Provara

Start here:
1. **Tutorial 1:** Your First Vault — understand the basics
2. **Tutorial 3:** Checkpoint & Query — learn to work with events
3. **Tutorial 2:** Multi-Actor Dispute — understand conflict resolution
4. **Tutorial 4:** MCP Integration — connect to AI agents
5. **Tutorial 5:** Anchor to L2 — add external trust anchors

### For AI Agent Builders

Jump to:
1. **Tutorial 1:** Your First Vault — quick start
2. **Tutorial 4:** MCP Integration — connect your agent
3. **Tutorial 5:** Anchor to L2 — add verifiable timestamps

### For Legal/Compliance Use Cases

Focus on:
1. **Tutorial 1:** Your First Vault — basics
2. **Tutorial 5:** Anchor to L2 — timestamps and legal admissibility
3. **Tutorial 3:** Checkpoint & Query — evidence retrieval

---

## Prerequisites

| Tutorial | Requires |
|----------|----------|
| 1 | Python 3.10+, pip |
| 2 | Tutorial 1 |
| 3 | Tutorial 1 |
| 4 | Tutorial 1, Node.js 18+ (for MCP host) |
| 5 | Tutorial 1, basic blockchain concepts |

---

## Quick Start

```bash
# Install Provara
pip install provara-protocol

# Create your first vault
provara init my_vault --actor "alice" --private-keys alice_keys.json

# Append an event
provara append my_vault \
  --type OBSERVATION \
  --data '{"subject": "getting_started", "predicate": "status", "value": "ready"}' \
  --keyfile alice_keys.json

# Verify integrity
provara verify my_vault
```

---

## What You'll Learn

By completing all tutorials:

1. **Vault Creation:** Initialize tamper-evident event logs
2. **Event Appending:** Add signed observations, assertions, attestations
3. **Conflict Resolution:** Handle multi-agent disputes
4. **State Management:** Checkpoints, queries, fast recovery
5. **External Anchors:** RFC 3161 timestamps, L2 blockchain commitments
6. **MCP Integration:** Connect AI agents to verifiable memory

---

## Next Steps After Tutorials

- **Protocol Spec:** [`BACKPACK_PROTOCOL_v1.0.md`](../BACKPACK_PROTOCOL_v1.0.md)
- **API Reference:** [`../api/`](../api/)
- **Comparison Matrix:** [`../COMPARISON.md`](../COMPARISON.md) (coming soon)
- **GitHub Repo:** https://github.com/provara-protocol/provara

---

## Support

- **Issues:** https://github.com/provara-protocol/provara/issues
- **Documentation:** https://provara.dev/docs
- **Protocol Spec:** https://provara.dev/spec/v1.0
