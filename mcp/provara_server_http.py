#!/usr/bin/env python3
"""
Provara MCP Server (HTTP/SSE Transport)
========================================
Model Context Protocol server with Server-Sent Events transport.
Compatible with Smithery.ai and browser-based MCP clients.

Usage:
    python provara_server_http.py [--port 8080] [--host 127.0.0.1]

Requirements:
    - Flask >= 3.0 (pip install flask)
    - flask-cors (pip install flask-cors)
"""

import argparse
import json
import sys
from pathlib import Path
from flask import Flask, request, Response, stream_with_context
from flask_cors import CORS

# Add SNP_Core/bin to path
_project_root = Path(__file__).resolve().parent.parent
_snp_core_bin = _project_root / "SNP_Core" / "bin"
if str(_snp_core_bin) not in sys.path:
    sys.path.insert(0, str(_snp_core_bin))

# Import the core server logic
from provara_server import ProvaraMCPServer


# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)  # Enable CORS for browser clients

server = ProvaraMCPServer()


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return {"status": "healthy", "server": "provara-mcp", "version": "1.0.0"}


@app.route('/sse', methods=['GET'])
def sse():
    """Server-Sent Events endpoint for streaming responses."""
    def generate():
        # SSE format: data: {json}\n\n
        # Send server info on connect
        info = {
            "type": "server_info",
            "server": "provara-mcp",
            "version": "1.0.0",
            "transport": "http/sse"
        }
        yield f"data: {json.dumps(info)}\n\n"
        
        # Keep connection alive
        # In a real implementation, this would handle ongoing requests
        while True:
            yield ": keepalive\n\n"
            import time
            time.sleep(30)
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@app.route('/mcp', methods=['POST'])
def mcp_request():
    """Handle MCP JSON-RPC requests over HTTP POST."""
    try:
        request_data = request.get_json()
        if not request_data:
            return {"error": {"code": -32700, "message": "Parse error"}}, 400
        
        response = server.handle_request(request_data)
        return response
    
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": request_data.get("id") if request_data else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }, 500


@app.route('/batch', methods=['POST'])
def batch_request():
    """Handle batched MCP requests."""
    try:
        requests = request.get_json()
        if not isinstance(requests, list):
            return {"error": {"code": -32600, "message": "Invalid Request"}}, 400
        
        responses = [server.handle_request(req) for req in requests]
        return responses
    
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }, 500


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Provara MCP Server (HTTP/SSE)")
    parser.add_argument('--port', type=int, default=8080, help="Port to listen on")
    parser.add_argument('--host', default='127.0.0.1', help="Host to bind to")
    parser.add_argument('--debug', action='store_true', help="Enable debug mode")
    args = parser.parse_args()
    
    print(f"🦞 Provara MCP Server starting on http://{args.host}:{args.port}")
    print(f"   Endpoints:")
    print(f"     GET  /health     - Health check")
    print(f"     POST /mcp        - MCP JSON-RPC requests")
    print(f"     POST /batch      - Batched requests")
    print(f"     GET  /sse        - Server-Sent Events stream")
    print()
    
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
