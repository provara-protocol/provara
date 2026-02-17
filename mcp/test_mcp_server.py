"""
test_mcp_server.py — Basic tests for Provara MCP Server
"""

import json
import subprocess
import sys
from pathlib import Path

def send_request(proc, request):
    """Send a JSON-RPC request to the server and read response."""
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    response_line = proc.stdout.readline()
    return json.loads(response_line)

def test_server():
    """Run basic MCP protocol tests."""
    server_path = Path(__file__).parent / "provara_server.py"
    
    proc = subprocess.Popen(
        [sys.executable, str(server_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    try:
        # Test 1: Initialize
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        response = send_request(proc, init_req)
        assert response.get("result", {}).get("protocolVersion") == "2024-11-05"
        assert response.get("result", {}).get("serverInfo", {}).get("name") == "provara"
        print("[OK] Initialize test passed")
        
        # Test 2: List tools
        list_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        response = send_request(proc, list_req)
        tools = response.get("result", {}).get("tools", [])
        assert len(tools) > 0
        tool_names = {t["name"] for t in tools}
        assert "bootstrap_vault" in tool_names
        assert "export_state" in tool_names
        assert "sync_vaults" in tool_names
        print(f"✓ Tools list test passed ({len(tools)} tools)")
        
        # Test 3: Invalid method
        invalid_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "invalid_method",
            "params": {}
        }
        
        response = send_request(proc, invalid_req)
        assert "error" in response
        assert response["error"]["code"] == -32601
        print("✓ Invalid method test passed")
        
        print("\n✅ All MCP server tests passed")
        
    finally:
        proc.terminate()
        proc.wait(timeout=5)

if __name__ == "__main__":
    test_server()
