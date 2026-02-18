# MCP Server Migration to FastMCP (Lane 4A)

**Status:** ✅ Complete  
**Date:** 2026-02-18  
**Protocol Version:** MCP Spec Revision 2025-06-18

## Summary

The Provara MCP server has been fully migrated to use the official `mcp.server.fastmcp.FastMCP` SDK. This migration provides:

- **Official SDK compliance** — Uses the canonical FastMCP framework
- **Structured output support** — Tools return both `content` (text) and `structuredContent` (JSON) per MCP spec
- **Multi-transport support** — Stdio for local agents, HTTP/SSE for remote clients
- **Automatic schema generation** — Python type hints drive JSON Schema generation
- **Backward compatibility** — All existing tool interfaces preserved

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              FastMCP Application Layer                  │
│  @MCP_APP.tool decorators register tool handlers        │
│  Automatic inputSchema generation from type hints       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              JSON-RPC Transport Layer                   │
│  handle_jsonrpc_request() routes MCP protocol methods:  │
│  - initialize, ping                                     │
│  - tools/list, tools/call                               │
│  - SSE session management                               │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Provara Core (psmc module)                 │
│  append_event, verify_chain, checkpoint_vault, etc.     │
└─────────────────────────────────────────────────────────┘
```

## Tool Catalog

All tools preserve identical argument structures for backward compatibility:

| Tool | Description | Key Args |
|------|-------------|----------|
| `append_event` | Append a signed event to a vault | `vault_path`, `event_type`, `data`, `tags?`, `emit_provara?` |
| `verify_chain` | Verify hash/signature chain integrity | `vault_path` |
| `snapshot_state` | Compute deterministic vault snapshot | `vault_path` |
| `snapshot_belief` | Alias for `snapshot_state` | `vault_path` |
| `query_timeline` | Query vault events with filters | `vault_path`, `event_type?`, `start_time?`, `end_time?`, `limit?` |
| `list_conflicts` | List conflicting high-confidence evidence | `vault_path` |
| `generate_digest` | Generate weekly digest markdown | `vault_path`, `weeks?` |
| `export_digest` | Alias for `generate_digest` | `vault_path`, `weeks?` |
| `export_markdown` | Export entire vault as Markdown | `vault_path` |
| `checkpoint_vault` | Create signed state snapshot | `vault_path` |

## Usage

### Stdio Mode (Default)

For local MCP clients (e.g., Claude Desktop, IDE agents):

```bash
python tools/mcp_server/server.py --transport stdio
```

Or simply:

```bash
python tools/mcp_server/server.py
```

### HTTP/SSE Mode

For remote clients or containerized deployments:

```bash
python tools/mcp_server/server.py --transport http --host 0.0.0.0 --port 8765
```

Connect via:
- SSE endpoint: `http://localhost:8765/sse`
- Health check: `http://localhost:8765/health`

### Docker

```bash
docker run --rm -p 8765:8765 provara/mcp-server:local
```

See [`docs/DOCKER_MCP.md`](DOCKER_MCP.md) for full Docker documentation.

## Structured Output

Per MCP spec revision 2025-06-18, all tool responses include both:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"event_id\": \"evt_abc123\", \"hash\": \"def456...\"}"
      }
    ],
    "structuredContent": {
      "event_id": "evt_abc123",
      "hash": "def456...",
      "timestamp": "2026-02-18T12:34:56Z"
    }
  }
}
```

This enables:
- **Human-readable output** via `content[0].text`
- **Machine-parseable output** via `structuredContent`

## Dependencies

The server requires the `fastmcp` extra:

```bash
pip install "mcp[fastmcp]>=0.1.0"
```

Runtime dependencies (from `requirements.txt`):
- `cryptography>=41.0` — Ed25519 signing
- `mcp[fastmcp]>=0.1.0` — FastMCP SDK

## Testing

All 22 MCP tests pass:

```bash
# Stdio tests (15 tests)
pytest tools/mcp_server/test_server.py::TestMCPServerStdio -v

# SSE tests (7 tests)
pytest tools/mcp_server/test_server.py::TestMCPServerSSE -v

# All MCP tests
pytest tools/mcp_server/test_server.py -v
```

## Breaking Changes

**None.** This migration maintains 100% backward compatibility with existing MCP clients. All tool interfaces, argument names, and response structures are preserved.

## Migration Notes

### What Changed

1. **Tool registration** — Moved from manual JSON-RPC handlers to `@MCP_APP.tool` decorators
2. **Schema generation** — Now automatic from Python type hints
3. **Transport abstraction** — FastMCP handles stdio/SSE routing
4. **Structured output** — Added `structuredContent` support per MCP spec

### What Stayed the Same

1. **Tool interfaces** — All argument names and types unchanged
2. **Response format** — JSON-RPC 2.0 structure preserved
3. **Vault operations** — All psmc module calls unchanged
4. **Error handling** — Same error codes and messages

## Future Enhancements

Potential improvements for future versions:

- **Progress reporting** — Use FastMCP `Context` for long-running operations
- **Logging integration** — Structured logging via MCP logging API
- **Resource exposure** — Expose vault files as MCP resources
- **Prompt templates** — Pre-built prompts for common vault operations

## References

- [MCP Specification](https://modelcontextprotocol.io/specification)
- [FastMCP Documentation](https://github.com/modelcontextprotocol/python-sdk)
- [Provara Protocol Spec](../PROTOCOL_PROFILE.txt)
