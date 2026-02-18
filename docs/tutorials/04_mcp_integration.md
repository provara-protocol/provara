# Tutorial 4: MCP Integration

**Reading time:** 5 minutes  
**Prerequisites:** Tutorial 1 completed, Node.js 18+ (for MCP host)

Connect a Provara vault to an AI agent via the Model Context Protocol (MCP). Your agent gains verifiable, tamper-evident memory.

---

## What is MCP?

The **Model Context Protocol (MCP)** lets AI agents access external tools and data sources. An MCP server exposes tools that agents can discover and invoke.

**Provara MCP Server** gives your agent:
- **Append-only memory:** Every observation is cryptographically signed
- **Verifiable history:** Hash chains detect tampering
- **Dispute resolution:** Multi-agent conflicts surface automatically
- **State snapshots:** Fast checkpoint/recovery

---

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌──────────────┐
│  AI Agent       │         │  MCP Server      │         │  Provara     │
│  (Claude, etc.) │◄───────►│  (stdio or SSE)  │◄───────►│  Vault       │
│                 │  MCP    │                  │  NDJSON │  (events)    │
└─────────────────┘         └──────────────────┘         └──────────────┘
```

---

## Step 1: Install the MCP Server

Clone the repo and install dependencies:

```bash
cd provara
pip install -e ".[dev]"
```

Verify the server works:

```bash
python tools/mcp_server/server.py --help
```

---

## Step 2: Create a Vault for Your Agent

```bash
provara init agent_memory --actor "claude_agent" --private-keys agent_keys.json
```

---

## Step 3: Run the MCP Server

### Option A: Stdio Mode (Local Agents)

For agents running on the same machine:

```bash
python tools/mcp_server/server.py --transport stdio
```

The server waits for MCP protocol messages on stdin/stdout.

### Option B: HTTP/SSE Mode (Remote Agents)

For agents in containers or remote hosts:

```bash
python tools/mcp_server/server.py --transport http --port 8765
```

Connect via SSE: `http://localhost:8765/sse`

### Option C: Docker

```bash
docker run --rm -p 8765:8765 -v $(pwd)/agent_memory:/vault provara/mcp-server:local
```

---

## Step 4: Configure Your MCP Host

### Claude Desktop (claude_desktop_config.json)

```json
{
  "mcpServers": {
    "provara": {
      "command": "python",
      "args": ["/path/to/provara/tools/mcp_server/server.py"],
      "env": {}
    }
  }
}
```

### Cursor IDE

Settings → MCP → Add Server:
- Name: `provara`
- Type: `stdio`
- Command: `python /path/to/provara/tools/mcp_server/server.py`

---

## Step 5: Available Tools

Once connected, your agent can use these tools:

| Tool | Description |
|------|-------------|
| `append_event` | Append a signed observation or assertion |
| `verify_chain` | Verify vault integrity |
| `snapshot_state` | Get current derived state |
| `query_timeline` | Query events by type/date |
| `list_conflicts` | List disputed claims |
| `checkpoint_vault` | Create fast-load checkpoint |
| `export_markdown` | Export vault as readable markdown |

---

## Step 6: Example Agent Interactions

### Append an Observation

**Agent prompt:**
> "Record that I analyzed file /app/main.py and found no security issues."

**MCP tool call:**
```json
{
  "tool": "append_event",
  "arguments": {
    "vault_path": "/path/to/agent_memory",
    "event_type": "OBSERVATION",
    "data": {
      "subject": "file_analysis",
      "predicate": "result",
      "value": {
        "file": "/app/main.py",
        "finding": "no_security_issues",
        "confidence": 0.95
      }
    }
  }
}
```

**Response:**
```json
{
  "event_id": "evt_3f8a2b9c1d4e5f6a",
  "timestamp": "2026-02-18T14:32:00Z",
  "state_hash": "a3f8b2c9d1e4f5a6..."
}
```

### Query Past Work

**Agent prompt:**
> "What did I observe about the database yesterday?"

**MCP tool call:**
```json
{
  "tool": "query_timeline",
  "arguments": {
    "vault_path": "/path/to/agent_memory",
    "event_type": "OBSERVATION",
    "start_time": "2026-02-17T00:00:00Z",
    "end_time": "2026-02-17T23:59:59Z"
  }
}
```

**Response:**
```json
{
  "events": [
    {
      "event_id": "evt_...",
      "type": "OBSERVATION",
      "payload": {
        "subject": "database",
        "predicate": "latency",
        "value": "45ms"
      }
    }
  ]
}
```

### Verify Memory Integrity

**Agent prompt:**
> "Verify my memory hasn't been tampered with."

**MCP tool call:**
```json
{
  "tool": "verify_chain",
  "arguments": {
    "vault_path": "/path/to/agent_memory"
  }
}
```

**Response:**
```json
{
  "valid": true
}
```

---

## Step 7: Multi-Agent Scenario

Two agents share a vault:

```bash
# Agent 1 (Alice) initializes
provara init shared_memory --actor "alice" --private-keys alice_keys.json

# Agent 2 (Bob) gets keys
# In production, Bob generates his own keypair
python -c "
from provara import BackpackKeypair
import json
kp = BackpackKeypair.generate()
print(json.dumps({kp.key_id: kp.private_key_b64}, indent=2))
" > bob_keys.json

# Both agents connect to the same vault via MCP
# Each signs their own observations
```

When Alice and Bob disagree, the reducer detects conflicts:

```bash
# Agent asks: "Are there any disputes?"
{
  "tool": "list_conflicts",
  "arguments": {
    "vault_path": "/path/to/shared_memory"
  }
}
```

---

## Why Provara MCP > Standard MCP Memory

| Feature | Standard MCP Memory | Provara MCP Memory |
|---------|---------------------|-------------------|
| **Integrity** | Trust the database | Cryptographic verification |
| **Tamper evidence** | None | Hash chain detects edits |
| **Non-repudiation** | None | Ed25519 signatures |
| **Disputes** | Last-write-wins | Contested namespace |
| **Audit** | Query logs | Verifiable event log |
| **Long-term** | Database schema drift | 50-year NDJSON format |

**The verifiability gap:** Standard MCP memory trusts the storage layer. Provara MCP memory *verifies* it.

---

## Troubleshooting

**"Server not found"**  
Ensure the MCP server is running and the path in your MCP host config is correct.

**"Vault not found"**  
Create the vault first: `provara init agent_memory --actor "my_agent"`

**"Permission denied"**  
Check file permissions on the vault directory and keys file.

---

## Next Steps

- **Tutorial 5:** Anchor to L2 — timestamp or anchor vault state to external trust anchor
- **MCP Documentation:** [`docs/MCP_MIGRATION.md`](MCP_MIGRATION.md)
- **Docker Deployment:** [`docs/DOCKER_MCP.md`](DOCKER_MCP.md)

---

**Reference:**  
- [MCP Specification](https://modelcontextprotocol.io/)  
- [Provara Event Types](../spec/event_types.md)
