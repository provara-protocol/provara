# MCP Server

**Module:** `tools/mcp_server/server.py`

Model Context Protocol integration. Connect any AI agent (Claude, GPT, etc.) to a Provara vault for tamper-evident memory.

## Quick Start

### Stdio Mode (Claude Code, Cursor)

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "provara": {
      "command": "python",
      "args": ["path/to/tools/mcp_server/server.py", "--transport", "stdio"]
    }
  }
}
```

### HTTP Mode (Claude.ai, OpenAI)

```bash
python tools/mcp_server/server.py --transport http --port 8765
# Connect to: http://localhost:8765/sse
```

## Available Tools

| Tool | Description |
|------|-------------|
| `append_event` | Write a signed event to the vault |
| `verify_chain` | Verify causal chain + signatures |
| `snapshot_state` | Get current state hash |
| `query_timeline` | Filter events by type/time |
| `list_conflicts` | Show contested beliefs |
| `generate_digest` | Weekly markdown digest |
| `export_markdown` | Full vault history as markdown |
| `checkpoint_vault` | Create signed state snapshot |

## Example: Agent with Memory

```python
# AI agent using Provara vault as persistent memory

from provara.cli import Vault

vault = Vault(Path("Agent_Memory"))

# Agent observes something
observation = {
    "type": "OBSERVATION",
    "subject": "conversation_2024_02_17",
    "predicate": "user_prefers",
    "value": "technical_explanations",
    "confidence": 0.85
}

vault.append_event(observation, key_id, private_key)

# Next session: agent recalls
state = vault.get_state()
preferences = state.canonical.get("conversation_2024_02_17:user_prefers")
# Returns: "technical_explanations" (with 0.85 confidence)
```

## References

- [MCP Specification](https://modelcontextprotocol.io/)
- [Provara: AI Agent Integration](https://provara.dev/docs/mcp/)
