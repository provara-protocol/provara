# Provara MCP Server

Model Context Protocol server exposing Provara Protocol operations.

## Features

**Available Tools:**
- `bootstrap_vault` — Create new Provara vault with cryptographic identity
- `verify_vault` — Run compliance checks on a vault
- `export_state` — Export belief state from event log
- `sync_vaults` — Sync two vaults (union merge + state recomputation)
- `verify_chain` — Verify causal chain integrity for all actors

**Transports:**
- **stdio** — JSON-RPC over stdin/stdout (standard MCP)
- **HTTP/SSE** — JSON-RPC over HTTP + Server-Sent Events (Smithery.ai compatible)

## Usage

### Stdio Transport

**Via Claude Desktop:**

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

**Direct invocation:**

```bash
python provara_server.py
```

The server reads JSON-RPC requests from stdin and writes responses to stdout.

### HTTP/SSE Transport

**Start the server:**

```bash
python provara_server_http.py --port 8080 --host 127.0.0.1
```

**Endpoints:**
- `GET /health` — Health check
- `POST /mcp` — MCP JSON-RPC requests
- `POST /batch` — Batched requests
- `GET /sse` — Server-Sent Events stream

**Make a request:**

```bash
curl -X POST http://127.0.0.1:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

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

**Stdio transport:**
```bash
python test_mcp_server.py
```

**HTTP transport:**
```bash
python test_http_server.py
```

Tests cover: initialize handshake, tool listing, error handling, and batch requests.

## Next Steps

- [x] Add HTTP/SSE transport for Smithery.ai compatibility ✅
- [ ] Add more Provara tools (key rotation, delta export/import, etc.)
- [ ] Add request validation schemas
- [ ] Add logging/observability
- [ ] Add authentication/authorization for HTTP transport

## Dependencies

**Core:**
- `cryptography >= 41.0` (via Provara SNP_Core)
- Python 3.10+

**HTTP transport only:**
- `flask >= 3.0`
- `flask-cors`
- `requests` (for testing)

Install HTTP dependencies:
```bash
pip install flask flask-cors requests
```

## License

Apache 2.0
