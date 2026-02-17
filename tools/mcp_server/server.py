"""
Minimal Provara MCP server with stdio and HTTP transports.

This implementation is intentionally dependency-free (stdlib only) and
provides a small JSON-RPC surface compatible with MCP-style tool calls.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import queue
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict


REPO_ROOT = Path(__file__).resolve().parents[2]
PSMC_DIR = REPO_ROOT / "tools" / "psmc"
if str(PSMC_DIR) not in sys.path:
    sys.path.insert(0, str(PSMC_DIR))

from psmc import (  # type: ignore
    append_event,
    checkpoint_vault,
    compute_vault_state,
    export_markdown,
    generate_digest,
    list_conflicts,
    query_timeline,
    verify_chain,
)


SERVER_INFO = {
    "name": "provara-mcp",
    "version": "0.1.0",
}

# Session storage for SSE transport: session_id -> queue.Queue
SSE_SESSIONS: Dict[str, queue.Queue[str]] = {}


def _jsonrpc_result(request_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _ensure_vault(params: Dict[str, Any]) -> Path:
    vault = Path(str(params.get("vault_path", ""))).expanduser().resolve()
    if not vault.is_dir():
        raise ValueError(f"vault_path is not a directory: {vault}")
    return vault


def _tool_append_event(args: Dict[str, Any]) -> Dict[str, Any]:
    vault = _ensure_vault(args)
    event_type = str(args.get("event_type") or "").strip()
    if not event_type:
        raise ValueError("event_type is required")
    data = args.get("data")
    if not isinstance(data, dict):
        raise ValueError("data must be an object")
    tags = args.get("tags")
    if tags is not None and not isinstance(tags, list):
        raise ValueError("tags must be an array when provided")
    emit_provara = bool(args.get("emit_provara", False))
    try:
        out = append_event(
            vault, event_type, data, tags=tags, emit_provara=emit_provara
        )
    except SystemExit as exc:
        raise ValueError(f"append_event rejected input: {exc}") from exc
    return {
        "event_id": out.get("event_id"),
        "hash": out.get("hash"),
        "timestamp": out.get("timestamp"),
        "provara_event_id": out.get("provara_event_id"),
        "state_hash": out.get("state_hash"),
    }


def _tool_verify_chain(args: Dict[str, Any]) -> Dict[str, Any]:
    vault = _ensure_vault(args)
    ok = verify_chain(vault, verbose=False)
    return {"valid": bool(ok)}


def _tool_generate_digest(args: Dict[str, Any]) -> Dict[str, Any]:
    vault = _ensure_vault(args)
    weeks_raw = args.get("weeks", 1)
    try:
        weeks = int(weeks_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("weeks must be an integer") from exc
    if weeks <= 0:
        raise ValueError("weeks must be > 0")
    digest = generate_digest(vault, weeks=weeks)
    return {"digest": digest}


def _tool_snapshot_state(args: Dict[str, Any]) -> Dict[str, Any]:
    vault = _ensure_vault(args)
    return compute_vault_state(vault)


def _tool_query_timeline(args: Dict[str, Any]) -> Dict[str, Any]:
    vault = _ensure_vault(args)
    events = query_timeline(
        vault,
        event_type=args.get("event_type"),
        start_time=args.get("start_time"),
        end_time=args.get("end_time"),
        limit=args.get("limit"),
    )
    return {"events": events}


def _tool_list_conflicts(args: Dict[str, Any]) -> Dict[str, Any]:
    vault = _ensure_vault(args)
    conflicts = list_conflicts(vault)
    return {"conflicts": conflicts}


def _tool_export_markdown(args: Dict[str, Any]) -> Dict[str, Any]:
    vault = _ensure_vault(args)
    content = export_markdown(vault)
    return {"markdown": content}


def _tool_checkpoint_vault(args: Dict[str, Any]) -> Dict[str, Any]:
    vault = _ensure_vault(args)
    return checkpoint_vault(vault)


TOOLS: Dict[str, Dict[str, Any]] = {
    "append_event": {
        "description": "Append a signed event to a PSMC/Provara vault.",
        "input_schema": {
            "type": "object",
            "required": ["vault_path", "event_type", "data"],
            "properties": {
                "vault_path": {"type": "string"},
                "event_type": {"type": "string"},
                "data": {"type": "object"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "emit_provara": {"type": "boolean"},
            },
        },
        "handler": _tool_append_event,
    },
    "verify_chain": {
        "description": "Verify hash/signature chain integrity for a vault.",
        "input_schema": {
            "type": "object",
            "required": ["vault_path"],
            "properties": {"vault_path": {"type": "string"}},
        },
        "handler": _tool_verify_chain,
    },
    "generate_digest": {
        "description": "Alias for export_digest.",
        "input_schema": {
            "type": "object",
            "required": ["vault_path"],
            "properties": {
                "vault_path": {"type": "string"},
                "weeks": {"type": "integer", "minimum": 1},
            },
        },
        "handler": _tool_generate_digest,
    },
    "export_digest": {
        "description": "Generate weekly digest markdown from recent memory events.",
        "input_schema": {
            "type": "object",
            "required": ["vault_path"],
            "properties": {
                "vault_path": {"type": "string"},
                "weeks": {"type": "integer", "minimum": 1},
            },
        },
        "handler": _tool_generate_digest,
    },
    "snapshot_belief": {
        "description": "Compute deterministic vault snapshot and state hash.",
        "input_schema": {
            "type": "object",
            "required": ["vault_path"],
            "properties": {"vault_path": {"type": "string"}},
        },
        "handler": _tool_snapshot_state,
    },
    "snapshot_state": {
        "description": "Alias for snapshot_belief.",
        "input_schema": {
            "type": "object",
            "required": ["vault_path"],
            "properties": {"vault_path": {"type": "string"}},
        },
        "handler": _tool_snapshot_state,
    },
    "query_timeline": {
        "description": "Query vault events with filters.",
        "input_schema": {
            "type": "object",
            "required": ["vault_path"],
            "properties": {
                "vault_path": {"type": "string"},
                "event_type": {"type": "string"},
                "start_time": {"type": "string"},
                "end_time": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
        "handler": _tool_query_timeline,
    },
    "list_conflicts": {
        "description": "List conflicting high-confidence evidence.",
        "input_schema": {
            "type": "object",
            "required": ["vault_path"],
            "properties": {"vault_path": {"type": "string"}},
        },
        "handler": _tool_list_conflicts,
    },
    "export_digest": {
        "description": "Generate weekly digest markdown from recent memory events.",
        "input_schema": {
            "type": "object",
            "required": ["vault_path"],
            "properties": {
                "vault_path": {"type": "string"},
                "weeks": {"type": "integer", "minimum": 1},
            },
        },
        "handler": _tool_generate_digest,
    },
    "export_markdown": {
        "description": "Export the entire vault history as a formatted Markdown document.",
        "input_schema": {
            "type": "object",
            "required": ["vault_path"],
            "properties": {"vault_path": {"type": "string"}},
        },
        "handler": _tool_export_markdown,
    },
    "checkpoint_vault": {
        "description": "Sign and save a new state snapshot (checkpoint) for faster loading.",
        "input_schema": {
            "type": "object",
            "required": ["vault_path"],
            "properties": {"vault_path": {"type": "string"}},
        },
        "handler": _tool_checkpoint_vault,
    },
}


def handle_jsonrpc_request(request: Dict[str, Any]) -> Dict[str, Any]:
    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}

    if request.get("jsonrpc") != "2.0" and method != "initialize":
        # Loose check for initialization
        pass

    if method == "initialize":
        return _jsonrpc_result(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "serverInfo": SERVER_INFO,
                "capabilities": {"tools": {}},
            },
        )

    if method == "ping":
        return _jsonrpc_result(request_id, {"ok": True})

    if method == "tools/list":
        tools = []
        for name, cfg in sorted(TOOLS.items()):
            tools.append(
                {
                    "name": name,
                    "description": cfg["description"],
                    "inputSchema": cfg["input_schema"],
                }
            )
        return _jsonrpc_result(request_id, {"tools": tools})

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if not isinstance(name, str):
            return _jsonrpc_error(request_id, -32602, "tools/call missing 'name'")
        if not isinstance(args, dict):
            return _jsonrpc_error(
                request_id, -32602, "tools/call 'arguments' must be an object"
            )
        tool = TOOLS.get(name)
        if tool is None:
            return _jsonrpc_error(request_id, -32601, f"Unknown tool: {name}")
        try:
            # Redirect stdout → stderr so tool diagnostic prints (e.g. psmc's
            # "Digest written: …" / "OK: … events verified") don't contaminate
            # the stdio JSON-RPC response stream.
            with contextlib.redirect_stdout(sys.stderr):
                data = tool["handler"](args)
        except ValueError as exc:
            return _jsonrpc_error(request_id, -32602, str(exc))
        except Exception as exc:
            return _jsonrpc_error(request_id, -32000, f"Tool failed: {exc}")
        return _jsonrpc_result(
            request_id,
            {
                "content": [{"type": "text", "text": json.dumps(data, sort_keys=True)}]
            },
        )

    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


def run_stdio() -> int:
    for line in sys.stdin:
        msg = line.strip()
        if not msg:
            continue
        try:
            req = json.loads(msg)
        except json.JSONDecodeError:
            resp = _jsonrpc_error(None, -32700, "Parse error")
        else:
            resp = handle_jsonrpc_request(req)
        sys.stdout.write(json.dumps(resp, separators=(",", ":")) + "\n")
        sys.stdout.flush()
    return 0


def _make_http_handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send_json(200, {"ok": True, "server": SERVER_INFO["name"]})
                return
            if self.path == "/sse":
                self._handle_sse()
                return
            self._send_json(404, {"error": "not_found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path.startswith("/message"):
                self._handle_message()
                return
            if self.path == "/mcp":
                # Legacy single-shot POST
                self._handle_legacy_post()
                return
            self._send_json(404, {"error": "not_found"})

        def _handle_sse(self) -> None:
            session_id = str(uuid.uuid4())
            q: queue.Queue[str] = queue.Queue()
            SSE_SESSIONS[session_id] = q

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            # Send initial endpoint event per MCP spec
            endpoint_url = f"/message?session_id={session_id}"
            self._send_sse_event("endpoint", endpoint_url)

            try:
                while True:
                    try:
                        msg = q.get(timeout=30)
                        self._send_sse_event("message", msg)
                    except queue.Empty:
                        # Keep-alive
                        self.wfile.write(b":\n\n")
                        self.wfile.flush()
            except (ConnectionResetError, BrokenPipeError):
                pass
            finally:
                if session_id in SSE_SESSIONS:
                    del SSE_SESSIONS[session_id]

        def _handle_message(self) -> None:
            # Parse session_id from query string
            from urllib.parse import parse_qs, urlparse

            query = parse_qs(urlparse(self.path).query)
            session_id = query.get("session_id", [None])[0]

            if not session_id or session_id not in SSE_SESSIONS:
                self._send_json(404, {"error": "session_not_found"})
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                req = json.loads(raw.decode("utf-8"))
            except Exception:
                self._send_json(400, {"error": "invalid_request"})
                return

            resp = handle_jsonrpc_request(req)
            # Send response back to SSE stream
            SSE_SESSIONS[session_id].put(json.dumps(resp))
            self.send_response(202)  # Accepted
            self.end_headers()

        def _handle_legacy_post(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                req = json.loads(raw.decode("utf-8"))
            except Exception:
                self._send_json(400, _jsonrpc_error(None, -32700, "Parse error"))
                return
            resp = handle_jsonrpc_request(req)
            self._send_json(200, resp)

        def _send_sse_event(self, event: str, data: str) -> None:
            msg = f"event: {event}\ndata: {data}\n\n"
            self.wfile.write(msg.encode("utf-8"))
            self.wfile.flush()

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, code: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def run_http(host: str, port: int) -> int:
    server = ThreadingHTTPServer((host, port), _make_http_handler())
    print(f"provara-mcp sse/http listening on http://{host}:{port}/sse")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Minimal Provara MCP server")
    ap.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode",
    )
    ap.add_argument("--host", default="127.0.0.1", help="HTTP host")
    ap.add_argument("--port", type=int, default=8765, help="HTTP port")
    args = ap.parse_args(argv)

    if args.transport == "stdio":
        return run_stdio()
    return run_http(args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
