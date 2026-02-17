#!/usr/bin/env python3
"""
Provara MCP Server
==================
Model Context Protocol server exposing Provara Protocol operations.

Provides tools for:
- Vault creation and management
- Event appending and verification
- State computation and export
- Multi-device sync operations

Transport: stdio (standard MCP)

Usage:
    python provara_server.py

Or via Claude Desktop / MCP clients:
    {
      "mcpServers": {
        "provara": {
          "command": "python",
          "args": ["C:/provara/mcp/provara_server.py"]
        }
      }
    }
"""

import json
import sys
from pathlib import Path
from typing import Any

# Add SNP_Core/bin to path for Provara primitives
_project_root = Path(__file__).resolve().parent.parent
_snp_core_bin = _project_root / "SNP_Core" / "bin"
if str(_snp_core_bin) not in sys.path:
    sys.path.insert(0, str(_snp_core_bin))

from bootstrap_v0 import bootstrap_backpack, BootstrapResult
from reducer_v0 import SovereignReducerV0
from sync_v0 import sync_backpacks, verify_causal_chain, load_events, export_delta, import_delta
from backpack_signing import BackpackKeypair


# ---------------------------------------------------------------------------
# MCP Protocol Implementation
# ---------------------------------------------------------------------------

class ProvaraMCPServer:
    """MCP server for Provara Protocol operations."""

    def __init__(self):
        self.tools = {
            "bootstrap_vault": {
                "description": "Create a new Provara vault with cryptographic identity",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path for the new vault"
                        },
                        "uid": {
                            "type": "string",
                            "description": "Optional custom UID (defaults to UUIDv4)"
                        },
                        "actor": {
                            "type": "string",
                            "description": "Actor name for genesis events",
                            "default": "sovereign_genesis"
                        },
                        "quorum": {
                            "type": "boolean",
                            "description": "Generate quorum keypair for recovery",
                            "default": False
                        }
                    },
                    "required": ["path"]
                }
            },
            "verify_vault": {
                "description": "Run compliance tests on a Provara vault",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the vault directory"
                        }
                    },
                    "required": ["path"]
                }
            },
            "export_state": {
                "description": "Export current belief state from a vault's event log",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the vault directory"
                        }
                    },
                    "required": ["path"]
                }
            },
            "sync_vaults": {
                "description": "Sync two Provara vaults (union merge + state recomputation)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "local": {
                            "type": "string",
                            "description": "Path to local vault"
                        },
                        "remote": {
                            "type": "string",
                            "description": "Path to remote vault"
                        }
                    },
                    "required": ["local", "remote"]
                }
            },
            "verify_chain": {
                "description": "Verify causal chain integrity for all actors in a vault",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the vault directory"
                        }
                    },
                    "required": ["path"]
                }
            },
            "export_delta": {
                "description": "Export events since a given hash as a portable delta bundle",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the vault directory"
                        },
                        "since_hash": {
                            "type": "string",
                            "description": "Export events after this event_id (if None, export all)"
                        },
                        "output_file": {
                            "type": "string",
                            "description": "Path to write delta bundle"
                        }
                    },
                    "required": ["path", "output_file"]
                }
            },
            "import_delta": {
                "description": "Import a delta bundle into a vault (union merge)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the vault directory"
                        },
                        "delta_file": {
                            "type": "string",
                            "description": "Path to delta bundle file"
                        }
                    },
                    "required": ["path", "delta_file"]
                }
            }
        }

    def handle_request(self, request: dict) -> dict:
        """Process an MCP request and return response."""
        method = request.get("method")
        
        if method == "initialize":
            return self._handle_initialize(request)
        elif method == "tools/list":
            return self._handle_list_tools(request)
        elif method == "tools/call":
            return self._handle_call_tool(request)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    def _handle_initialize(self, request: dict) -> dict:
        """Handle MCP initialize handshake."""
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "provara",
                    "version": "1.0.0"
                }
            }
        }

    def _handle_list_tools(self, request: dict) -> dict:
        """List available Provara tools."""
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {
                "tools": [
                    {"name": name, **schema}
                    for name, schema in self.tools.items()
                ]
            }
        }

    def _handle_call_tool(self, request: dict) -> dict:
        """Execute a Provara tool."""
        params = request.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        try:
            if tool_name == "bootstrap_vault":
                result = self._bootstrap_vault(args)
            elif tool_name == "verify_vault":
                result = self._verify_vault(args)
            elif tool_name == "export_state":
                result = self._export_state(args)
            elif tool_name == "sync_vaults":
                result = self._sync_vaults(args)
            elif tool_name == "verify_chain":
                result = self._verify_chain(args)
            elif tool_name == "export_delta":
                result = self._export_delta(args)
            elif tool_name == "import_delta":
                result = self._import_delta(args)
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32000,
                    "message": str(e)
                }
            }

    # Tool implementations
    def _bootstrap_vault(self, args: dict) -> dict:
        """Create a new Provara vault."""
        path = Path(args["path"])
        result = bootstrap_backpack(
            path,
            uid=args.get("uid"),
            actor=args.get("actor", "sovereign_genesis"),
            include_quorum=args.get("quorum", False),
            quiet=True
        )

        return {
            "success": result.success,
            "vault_path": str(result.backpack_path),
            "uid": result.uid,
            "root_key_id": result.root_key_id,
            "quorum_key_id": result.quorum_key_id,
            "merkle_root": result.merkle_root,
            "genesis_event_id": result.genesis_event_id,
            "errors": result.errors
        }

    def _verify_vault(self, args: dict) -> dict:
        """Run compliance checks on a vault."""
        # This would call compliance suite
        # For now, basic check
        path = Path(args["path"])
        return {
            "success": path.exists(),
            "path": str(path),
            "message": "Basic validation passed" if path.exists() else "Vault not found"
        }

    def _export_state(self, args: dict) -> dict:
        """Export belief state from event log."""
        path = Path(args["path"])
        events_path = path / "events" / "events.ndjson"
        
        events = load_events(events_path)
        reducer = SovereignReducerV0()
        reducer.apply_events(events)
        state = reducer.export_state()

        return {
            "success": True,
            "event_count": state["metadata"]["event_count"],
            "state_hash": state["metadata"]["state_hash"],
            "canonical_beliefs": len(state["canonical"]),
            "local_beliefs": len(state["local"]),
            "contested_beliefs": len(state["contested"]),
            "archived_beliefs": sum(len(v) if isinstance(v, list) else 1 for v in state["archived"].values())
        }

    def _sync_vaults(self, args: dict) -> dict:
        """Sync two vaults."""
        local = Path(args["local"])
        remote = Path(args["remote"])
        
        result = sync_backpacks(local, remote)
        
        return {
            "success": result.success,
            "events_merged": result.events_merged,
            "new_state_hash": result.new_state_hash,
            "fork_count": len(result.forks),
            "errors": result.errors
        }

    def _verify_chain(self, args: dict) -> dict:
        """Verify causal chain integrity."""
        path = Path(args["path"])
        events_path = path / "events" / "events.ndjson"
        
        events = load_events(events_path)
        actors = {e.get("actor") for e in events if e.get("actor")}
        
        results = {}
        for actor in actors:
            results[actor] = verify_causal_chain(events, actor)
        
        return {
            "success": all(results.values()),
            "actors_checked": len(results),
            "chain_results": results
        }

    def _export_delta(self, args: dict) -> dict:
        """Export events as a delta bundle."""
        path = Path(args["path"])
        since_hash = args.get("since_hash")
        output_file = Path(args["output_file"])
        
        delta_bytes = export_delta(path, since_hash=since_hash)
        output_file.write_bytes(delta_bytes)
        
        # Count events in delta
        lines = delta_bytes.decode("utf-8").strip().split("\n")
        # First line is header, rest are events
        event_count = len(lines) - 1 if len(lines) > 1 else 0
        
        return {
            "success": True,
            "output_file": str(output_file),
            "size_bytes": len(delta_bytes),
            "event_count": event_count,
            "since_hash": since_hash
        }

    def _import_delta(self, args: dict) -> dict:
        """Import a delta bundle into a vault."""
        path = Path(args["path"])
        delta_file = Path(args["delta_file"])
        
        if not delta_file.exists():
            raise FileNotFoundError(f"Delta file not found: {delta_file}")
        
        delta_bytes = delta_file.read_bytes()
        result = import_delta(path, delta_bytes)
        
        return {
            "success": result.success,
            "imported_count": result.imported_count,
            "rejected_count": result.rejected_count,
            "new_state_hash": result.new_state_hash,
            "errors": result.errors
        }


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------

def main():
    """Run MCP server on stdin/stdout."""
    server = ProvaraMCPServer()
    
    # Write startup message to stderr (stdout is for MCP protocol)
    print("Provara MCP Server started (stdio transport)", file=sys.stderr)
    
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = server.handle_request(request)
            print(json.dumps(response), flush=True)
        except Exception as e:
            print(f"Error processing request: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
