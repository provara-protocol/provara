# Provara MCP Server

**Persistent, verifiable memory for AI agents via the Model Context Protocol.**

The Provara MCP Server provides AI agents with tamper-evident memory through cryptographic event logs. Every observation, decision, and correction is signed, hashed, and chained — creating an auditable trail that can be independently verified. Unlike mutable databases or vector stores, Provara memory cannot be silently altered, making it ideal for high-stakes applications where trust and accountability matter.

---

## Quick Start

### 1. Install

```bash
pip install provara-protocol
```

The MCP server ships with the Provara protocol package.

### 2. Initialize a Vault

```bash
provara init my_agent_vault --actor "claude_agent"
```

### 3. Start the Server

**Stdio mode (Claude Desktop):**
```bash
python -m provara.mcp --transport stdio --vault-path ./my_agent_vault
```

**HTTP/SSE mode (API access):**
```bash
python -m provara.mcp --transport http --host 0.0.0.0 --port 8765 --vault-path ./my_agent_vault
```

**Docker:**
```bash
docker compose up provara-mcp
```

You now have a working MCP server with verifiable memory.

---

## Available Tools

| Tool | Description |
|------|-------------|
| `append_event` | Append a signed event to the vault |
| `verify_chain` | Verify hash/signature chain integrity |
| `generate_digest` | Generate weekly digest markdown from recent events |
| `export_digest` | Alias for `generate_digest` |
| `snapshot_belief` | Compute deterministic vault snapshot and state hash |
| `snapshot_state` | Alias for `snapshot_belief` |
| `query_timeline` | Query vault events with filters (type, time range, limit) |
| `list_conflicts` | List conflicting high-confidence evidence |
| `export_markdown` | Export entire vault history as formatted Markdown |
| `checkpoint_vault` | Create signed state snapshot for fast replay |

---

## Configuration

### Transport Options

**Stdio** (for Claude Desktop, local agents):
```bash
python -m provara.mcp --transport stdio --vault-path ./vault
```

**HTTP/SSE** (for remote agents, API access):
```bash
python -m provara.mcp --transport http --host 0.0.0.0 --port 8765 --vault-path ./vault
```

### Required Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--vault-path` | Path to Provara vault directory | (required) |
| `--transport` | Transport mode: `stdio` or `http` | `stdio` |

### Optional Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--host` | HTTP bind address (HTTP mode only) | `127.0.0.1` |
| `--port` | HTTP port (HTTP mode only) | `8765` |
| `--keyfile` | Path to private keys for signing | `vault/identity/private_keys.json` |

---

## Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

**Stdio mode:**
```json
{
  "mcpServers": {
    "provara": {
      "command": "python",
      "args": [
        "-m",
        "provara.mcp",
        "--transport",
        "stdio",
        "--vault-path",
        "/path/to/your/vault"
      ]
    }
  }
}
```

**HTTP/SSE mode:**
```json
{
  "mcpServers": {
    "provara": {
      "type": "http",
      "url": "http://localhost:8765/sse"
    }
  }
}
```

---

## Docker Deployment

### Quick Start

```bash
docker compose up provara-mcp
```

### Docker Compose Configuration

```yaml
services:
  provara-mcp:
    image: provara/mcp-server:latest
    ports:
      - "8765:8765"
    volumes:
      - ./vault:/app/vault
    environment:
      - VAULT_PATH=/app/vault
      - TRANSPORT=http
      - HOST=0.0.0.0
      - PORT=8765
    restart: unless-stopped
```

### Build Your Own Image

```bash
docker build -t provara/mcp-server:latest -f tools/mcp_server/Dockerfile .
```

---

## Tool Examples

### Append an Observation

```json
{
  "tool": "append_event",
  "arguments": {
    "vault_path": "/app/vault",
    "event_type": "OBSERVATION",
    "data": {
      "subject": "research_finding",
      "predicate": "discovered",
      "value": "LLM agents benefit from verifiable memory",
      "confidence": 0.85
    }
  }
}
```

**Response:**
```json
{
  "event_id": "evt_abc123...",
  "hash": "sha256:def456...",
  "timestamp": "2026-02-18T10:30:00Z",
  "state_hash": "sha256:ghi789..."
}
```

### Verify Memory Integrity

```json
{
  "tool": "verify_chain",
  "arguments": {
    "vault_path": "/app/vault"
  }
}
```

**Response:**
```json
{
  "valid": true
}
```

### Query Past Observations

```json
{
  "tool": "query_timeline",
  "arguments": {
    "vault_path": "/app/vault",
    "event_type": "OBSERVATION",
    "start_time": "2026-02-18T00:00:00Z",
    "limit": 10
  }
}
```

**Response:**
```json
{
  "events": [
    {
      "event_id": "evt_abc123...",
      "type": "OBSERVATION",
      "timestamp": "2026-02-18T10:30:00Z",
      "data": {...}
    }
  ]
}
```

---

## Troubleshooting

### "Vault not found" Error

**Problem:** The specified `--vault-path` does not exist.

**Solution:**
```bash
# Initialize a new vault first
provara init /path/to/vault --actor "my_agent"
```

### "Invalid event_type" Error

**Problem:** The `event_type` field is empty or missing.

**Solution:** Ensure `event_type` is a non-empty string:
```json
{
  "event_type": "OBSERVATION",  // Required, non-empty
  "data": {...}
}
```

### "Data must be an object" Error

**Problem:** The `data` field is not a JSON object.

**Solution:** Provide `data` as an object, not a string:
```json
// Wrong
"data": "some string"

// Correct
"data": {
  "subject": "topic",
  "value": "content"
}
```

### HTTP Server Won't Start

**Problem:** Port 8765 is already in use.

**Solution:** Use a different port:
```bash
python -m provara.mcp --transport http --port 8766
```

### SSE Connection Fails

**Problem:** Claude Desktop cannot connect via SSE.

**Solution:**
1. Ensure server is running with `--transport http`
2. Check firewall allows port 8765
3. Verify URL in config: `http://localhost:8765/sse`

### "Chain verification failed" Error

**Problem:** Vault integrity check detected tampering or corruption.

**Solution:**
1. Check if `events.ndjson` was manually edited (don't do this)
2. Restore from a backup: `provara backup /path/to/vault --restore`
3. Contact support if issue persists

---

## Version Compatibility

| MCP Server | Provara Protocol | Python |
|------------|------------------|--------|
| 0.3.0 | >=1.0.0 | 3.10+ |

---

## Security Considerations

- **Private keys:** Guard `private_keys.json` — anyone with access can sign events as your agent
- **Vault backups:** Regularly backup your vault: `provara backup /path/to/vault`
- **Access control:** HTTP mode binds to all interfaces by default — use `--host 127.0.0.1` for local-only access
- **Audit trail:** The vault is append-only — events cannot be deleted, only corrected with new events

---

## Development

### Run Tests

```bash
cd tools/mcp_server
python -m pytest test_server.py test_server_expansion.py -v
```

### Add a New Tool

1. Define handler function in `server.py`:
```python
def _tool_my_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    vault = _ensure_vault(args)
    # ... implementation ...
    return {"result": "value"}
```

2. Add to TOOLS dictionary with schema and description

3. Register with FastMCP:
```python
@MCP_APP.tool(name="my_tool", description="...")
async def my_tool(...):
    ...
```

---

## See Also

- [Provara Protocol Documentation](https://provara.dev/docs)
- [MCP Migration Guide](../../docs/MCP_MIGRATION.md)
- [Docker Deployment Guide](../../docs/DOCKER_MCP.md)
- [Claude Agent Demo](../../demos/claude_agent_vault_memory.md)

---

**License:** Apache 2.0  
**Repository:** https://github.com/provara-protocol/provara
