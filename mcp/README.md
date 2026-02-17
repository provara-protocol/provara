# Provara MCP Server

Model Context Protocol server exposing Provara Protocol operations.

## Features

**Available Tools:**
- `bootstrap_vault` — Create new Provara vault with cryptographic identity
- `verify_vault` — Run compliance checks on a vault
- `export_state` — Export belief state from event log
- `sync_vaults` — Sync two vaults (union merge + state recomputation)
- `verify_chain` — Verify causal chain integrity for all actors

**Transport:** stdio (standard MCP)

## Usage

### Via Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "provara": {
      "command": "python",
      "args": ["C:/provara/mcp/provara_server.py"]
    }
  }
}
```

### Direct Invocation

```bash
python provara_server.py
```

The server reads JSON-RPC requests from stdin and writes responses to stdout.

### Example Request

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "bootstrap_vault",
    "arguments": {
      "path": "/tmp/my_vault",
      "actor": "device_alpha",
      "quorum": true
    }
  }
}
```

## Testing

```bash
python test_mcp_server.py
```

Runs basic protocol tests: initialize handshake, tool listing, and error handling.

## Next Steps

- [ ] Add HTTP/SSE transport for Smithery.ai compatibility
- [ ] Add more Provara tools (key rotation, delta export/import, etc.)
- [ ] Add request validation schemas
- [ ] Add logging/observability

## Dependencies

- `cryptography >= 41.0` (via Provara SNP_Core)
- Python 3.10+

## License

Apache 2.0
